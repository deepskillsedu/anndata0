from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import threading

from app.history_reader import get_actual_history
from app.history_logger import start_history_logger
from app.sensor_router import start_sensor_router

from app.ditto_reader import (
    LEGACY_THING_ID,
    thing_id_for_farm,
    get_twin,
    get_actual,
    get_virtual,
    get_attributes
)

from app.ditto_writer import (
    update_virtual_properties,
    update_actual_properties
)

from app.farm_registry import (
    create_farm as create_farm_thing,
    list_farm_thing_ids,
    delete_farm as delete_farm_thing
)

from app.sensor_registry import (
    ensure_registry,
    get_all_sensors,
    rename_sensor,
    map_sensor_to_farm,
    acknowledge_sensor
)

app = FastAPI(
    title="Smart Farm Digital Twin",
    version="2.1.0"
)


@app.on_event("startup")
def startup():
    thread = threading.Thread(target=start_history_logger, daemon=True)
    thread.start()
    print("History Logger Started")

    try:
        ensure_registry()
        print("Sensor Registry Ready")
    except Exception as e:
        print("Sensor registry init error:", e)

    router_thread = threading.Thread(target=start_sensor_router, daemon=True)
    router_thread.start()
    print("Sensor Router Started")


# ---- models ----

class FarmCreate(BaseModel):
    name: str
    field: Optional[str] = None
    crop: Optional[str] = None

class SensorRename(BaseModel):
    name: str

class SensorMap(BaseModel):
    farm_id: Optional[str] = None


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

@app.patch("/sensors/{raw_key}/rename")
def rename(raw_key: str, payload: SensorRename):
    try:
        return rename_sensor(raw_key, payload.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/sensors/{raw_key}/map")
def map_farm(raw_key: str, payload: SensorMap):
    try:
        return map_sensor_to_farm(raw_key, payload.farm_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sensors/{raw_key}/acknowledge")
def ack_sensor(raw_key: str):
    try:
        return acknowledge_sensor(raw_key)
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
    """Permanently removes a farm from Ditto. The dashboard's 'Remove'
    button calls this so a deleted farm actually stays gone on refresh,
    instead of only being hidden in that one browser tab."""
    try:
        return delete_farm_thing(farm_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- legacy (Farm 1 / twin01) ----

@app.get("/farm/twin")
def farm_twin():
    return get_twin()

@app.get("/farm/digital-twin")
def digital_twin():
    return {
        "attributes": get_attributes(),
        "actual": get_actual(),
        "virtual": get_virtual()
    }

@app.get("/farm/attributes")
def attributes():
    return get_attributes()

@app.get("/farm/actual")
def actual():
    return get_actual()

@app.get("/farm/virtual")
def virtual():
    return get_virtual()

@app.post("/farm/virtual")
def update_virtual(properties: dict):
    return update_virtual_properties(properties)

@app.post("/farm/actual")
def update_actual(properties: dict):
    return update_actual_properties(properties)

@app.get("/farm/history/actual")
def actual_history():
    return get_actual_history(LEGACY_THING_ID)


# ---- farm-scoped ----

@app.get("/farm/{farm_id}/twin")
def farm_twin_scoped(farm_id: str):
    return get_twin(thing_id_for_farm(farm_id))

@app.get("/farm/{farm_id}/digital-twin")
def digital_twin_scoped(farm_id: str):
    thing_id = thing_id_for_farm(farm_id)
    return {
        "attributes": get_attributes(thing_id),
        "actual": get_actual(thing_id),
        "virtual": get_virtual(thing_id)
    }

@app.get("/farm/{farm_id}/attributes")
def farm_attributes_scoped(farm_id: str):
    return get_attributes(thing_id_for_farm(farm_id))

@app.get("/farm/{farm_id}/actual")
def farm_actual_scoped(farm_id: str):
    return get_actual(thing_id_for_farm(farm_id))

@app.get("/farm/{farm_id}/virtual")
def farm_virtual_scoped(farm_id: str):
    return get_virtual(thing_id_for_farm(farm_id))

@app.post("/farm/{farm_id}/virtual")
def update_farm_virtual_scoped(farm_id: str, properties: dict):
    return update_virtual_properties(properties, thing_id_for_farm(farm_id))

@app.post("/farm/{farm_id}/actual")
def update_farm_actual_scoped(farm_id: str, properties: dict):
    return update_actual_properties(properties, thing_id_for_farm(farm_id))

@app.get("/farm/{farm_id}/history/actual")
def farm_actual_history_scoped(farm_id: str):
    return get_actual_history(thing_id_for_farm(farm_id))


@app.get("/dashboard")
def dashboard():
    return FileResponse("templates/dashboard.html")
