from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import threading
import requests

from app.history_reader import get_actual_history, get_virtual_history, get_raw_sensor_history
from app.history_logger import start_history_logger

from app.ditto_reader import (
    thing_id_for_farm,
    get_twin,
    get_actual,
    get_virtual,
    get_attributes,
    get_scenarios
)

from app.ditto_writer import (
    update_virtual_properties,
    update_actual_properties,
    save_scenarios,
    FarmNotFoundError
)

from app.farm_registry import (
    create_farm as create_farm_thing,
    delete_farm as delete_farm_thing,
    list_farm_thing_ids
)

from app.sensor_registry import (
    ensure_catalog,
    seed_virtual_sensors,
    get_all_sensors,
    get_sensor,
    rename_sensor,
    map_sensor_to_farm,
    map_sensor_to_farms,
    add_sensor_mapping,
    remove_sensor_mapping,
    set_channel_range,
    set_channel_enabled,
    set_sensor_source,
    acknowledge_sensor
)

app = FastAPI(
    title="Smart Farm Digital Twin",
    version="2.2.0"
)


@app.on_event("startup")
def startup():
    thread = threading.Thread(target=start_history_logger, daemon=True)
    thread.start()
    print("History Logger Started")

    try:
        ensure_catalog()
        seed_virtual_sensors(list_farm_thing_ids())
        print("Sensor Catalog Ready")
    except Exception as e:
        print("Sensor catalog init error:", e)


# ---- models ----

class FarmCreate(BaseModel):
    name: str
    field: Optional[str] = None
    crop: Optional[str] = None

class SensorRename(BaseModel):
    name: str

class SensorMap(BaseModel):
    # back-compat single-farm shape — sets mappings to exactly this one farm
    farm_id: Optional[str] = None

class SensorMapping(BaseModel):
    farmId: str
    channels: Optional[List[str]] = None   # null/omitted = every channel

class SensorMappingList(BaseModel):
    mappings: List[SensorMapping]

class SensorAddMapping(BaseModel):
    farm_id: str
    channels: Optional[List[str]] = None

class SensorRemoveMapping(BaseModel):
    farm_id: str

class SensorSource(BaseModel):
    source: str   # "real" or "virtual"

class ChannelRange(BaseModel):
    channel: str
    min: Optional[float] = None
    max: Optional[float] = None

class ChannelEnabled(BaseModel):
    channel: str
    enabled: bool


# ---- basic ----

@app.get("/")
def root():
    return {
        "project": "Smart Farm Digital Twin",
        "architecture": "Ditto First",
        "status": "running"
    }

@app.get("/health")
def health():
    return {"backend": "healthy", "source": "Eclipse Ditto"}


# ---- stats ----

@app.get("/stats")
def stats():
    farm_count = 0
    try:
        farm_count = len(list_farm_thing_ids())
    except Exception:
        pass

    sensors = []
    try:
        sensors = get_all_sensors()
    except Exception:
        pass

    return {
        "totalFarms": farm_count,
        "totalSensors": len(sensors),
        "newSensors": sum(1 for s in sensors if s["isNew"])
    }


# ---- sensor registry ----

@app.get("/sensors")
def list_sensors():
    return {"sensors": get_all_sensors()}

@app.get("/sensors/{key}")
def get_sensor_detail(key: str):
    sensor = get_sensor(key)
    if not sensor:
        raise HTTPException(status_code=404, detail="sensor not found")
    return sensor

@app.patch("/sensors/{key}/rename")
def rename(key: str, payload: SensorRename):
    try:
        return rename_sensor(key, payload.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/sensors/{key}/map")
def map_farm(key: str, payload: SensorMap):
    """
    Back-compat single-farm mapping — sets this as the ONLY farm mapping,
    replacing any others. Kept for old callers; use /mappings below to
    add a second farm without removing the first.
    """
    try:
        return map_sensor_to_farm(key, payload.farm_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/sensors/{key}/mappings")
def replace_mappings(key: str, payload: SensorMappingList):
    """Replace the sensor's full list of farm mappings in one call."""
    try:
        mappings = [m.dict() for m in payload.mappings]
        return map_sensor_to_farms(key, mappings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sensors/{key}/mappings")
def add_mapping(key: str, payload: SensorAddMapping):
    """
    Add one farm mapping without touching existing ones — this is what
    lets the same sensor feed a second (or third...) farm. Re-posting
    the same farm_id updates that mapping's channel subset in place.
    """
    try:
        return add_sensor_mapping(key, payload.farm_id, payload.channels)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/sensors/{key}/mappings/{farm_id}")
def delete_mapping(key: str, farm_id: str):
    """Remove just one farm mapping, leaving any others on this sensor untouched."""
    try:
        return remove_sensor_mapping(key, farm_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/sensors/{key}/source")
def change_source(key: str, payload: SensorSource):
    try:
        return set_sensor_source(key, payload.source)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/sensors/{key}/range")
def update_channel_range(key: str, payload: ChannelRange):
    """
    Save min/max for one channel, server-side, in the sensor catalog.
    This is the endpoint the Settings/Sensors page Save button calls —
    it survives refresh and applies the same for every viewer, unlike
    the old browser-only min/max edit.
    """
    try:
        return set_channel_range(key, payload.channel, payload.min, payload.max)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/sensors/{key}/enabled")
def update_channel_enabled(key: str, payload: ChannelEnabled):
    """
    Turn one channel on/off, server-side. history_logger's sync loop
    checks this before forwarding a reading into any mapped farm, so
    'off' actually stops the data instead of just hiding it locally.
    """
    try:
        return set_channel_enabled(key, payload.channel, payload.enabled)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sensors/{key}/acknowledge")
def ack_sensor(key: str):
    try:
        return acknowledge_sensor(key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- farm management ----

@app.post("/farms")
def create_farm(payload: FarmCreate):
    return create_farm_thing(payload.name, payload.field, payload.crop)

@app.get("/farms")
def list_farms():
    farms = []
    for thing_id in list_farm_thing_ids():
        farm_id = thing_id.split(":", 1)[1]
        try:
            attrs = get_attributes(thing_id)
        except Exception:
            attrs = {}
        farms.append({
            "farm_id": farm_id,
            "thing_id": thing_id,
            "name": attrs.get("name", farm_id),
            "field": attrs.get("field"),
            "crop": attrs.get("crop"),
        })
    return {"farms": farms}

@app.delete("/farms/{farm_id}")
def delete_farm(farm_id: str):
    try:
        return delete_farm_thing(farm_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- farm-scoped ----
# No "legacy" farm anymore — every route below requires a real farm_id
# that maps to a thing actually created via POST /farms. A bad/deleted
# farm_id now returns a clean 404 instead of either crashing or
# silently falling back to some default thing.

@app.get("/farm/{farm_id}/twin")
def farm_twin_scoped(farm_id: str):
    try:
        return get_twin(thing_id_for_farm(farm_id))
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"farm '{farm_id}' not found")
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/farm/{farm_id}/digital-twin")
def digital_twin_scoped(farm_id: str):
    thing_id = thing_id_for_farm(farm_id)
    try:
        return {
            "attributes": get_attributes(thing_id),
            "actual": get_actual(thing_id),
            "virtual": get_virtual(thing_id)
        }
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"farm '{farm_id}' not found")
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/farm/{farm_id}/attributes")
def farm_attributes_scoped(farm_id: str):
    try:
        return get_attributes(thing_id_for_farm(farm_id))
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"farm '{farm_id}' not found")
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/farm/{farm_id}/actual")
def farm_actual_scoped(farm_id: str):
    try:
        return get_actual(thing_id_for_farm(farm_id))
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"farm '{farm_id}' not found")
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/farm/{farm_id}/virtual")
def farm_virtual_scoped(farm_id: str):
    try:
        return get_virtual(thing_id_for_farm(farm_id))
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"farm '{farm_id}' not found")
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/farm/{farm_id}/virtual")
def update_farm_virtual_scoped(farm_id: str, properties: dict):
    try:
        return update_virtual_properties(properties, thing_id_for_farm(farm_id))
    except FarmNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/farm/{farm_id}/actual")
def update_farm_actual_scoped(farm_id: str, properties: dict):
    try:
        return update_actual_properties(properties, thing_id_for_farm(farm_id))
    except FarmNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/farm/{farm_id}/history/actual")
def farm_actual_history_scoped(farm_id: str):
    return get_actual_history(thing_id_for_farm(farm_id))

@app.get("/farm/{farm_id}/history/virtual")
def farm_virtual_history_scoped(farm_id: str):
    return get_virtual_history(thing_id_for_farm(farm_id))

@app.get("/sensors/{key}/history/raw")
def sensor_raw_history_scoped(key: str):
    """
    Exact, untouched readings for one real device sensor (e.g. key='s01' ->
    device thing 'smartfarm:s01') — straight off the hardware, with no
    farm-mapping filtering or off-channel simulation applied. This is the
    ground-truth counterpart to /farm/{farm_id}/history/actual, which shows
    twin-processed (post-filter, post-simulation) data instead.
    """
    return get_raw_sensor_history(f"smartfarm:{key}")
 

@app.get("/farm/{farm_id}/scenarios")
def farm_scenarios_scoped(farm_id: str):
    try:
        return get_scenarios(thing_id_for_farm(farm_id))
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"farm '{farm_id}' not found")
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/farm/{farm_id}/scenarios")
def save_farm_scenarios_scoped(farm_id: str, scenarios: dict):
    try:
        return save_scenarios(scenarios, thing_id_for_farm(farm_id))
    except FarmNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/dashboard")
def dashboard():
    return FileResponse("templates/dashboard.html")