from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import threading

from app.history_reader import get_actual_history
from app.history_logger import start_history_logger

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
    list_farm_thing_ids
)

app = FastAPI(
    title="Smart Farm Digital Twin",
    version="2.1.0"
)


@app.on_event("startup")
def startup():

    thread = threading.Thread(
        target=start_history_logger,
        daemon=True
    )

    thread.start()

    print("History Logger Started")


# models

class FarmCreate(BaseModel):
    name: str
    field: Optional[str] = None
    crop: Optional[str] = None


# basic endpoints

@app.get("/")
def root():
    return {
        "project": "Smart Farm Digital Twin",
        "architecture": "Ditto First",
        "status": "running"
    }


@app.get("/health")
def health():
    return {
        "backend": "healthy",
        "source": "Eclipse Ditto"
    }


# ---- farm management ----

@app.post("/farms")
def create_farm(payload: FarmCreate):
    return create_farm_thing(payload.name, payload.field, payload.crop)


@app.get("/farms")
def list_farms():
    farms = []
    for thing_id in list_farm_thing_ids():
        if thing_id == LEGACY_THING_ID:
            continue
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


# ---- farm-scoped (every farm created through the dashboard) ----

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
    return FileResponse(
        "templates/dashboard.html"
    )