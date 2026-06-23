from datetime import datetime

from app.mongodb_service import (
    actual_sensor_history,
    actual_override_history,
    virtual_history,
    virtual_sensor_history,
    raw_sensor_history
)
from app.ditto_reader import get_twin


def _farm_name_for(thing_id: str) -> str:
    """
    Look up the human-readable farm name (attributes.name in Ditto) for
    a farm thingId, so every history document is self-describing without
    needing to join back to Ditto later.

    No caching here on purpose — this only runs for farm-related history
    (actual/virtual snapshots every 30s, plus discrete edit events), not
    for the raw per-sensor snapshot loop, so call volume stays low. If
    the Ditto lookup fails for any reason (farm deleted mid-write, Ditto
    briefly unreachable, etc.), fall back to thing_id rather than letting
    a name lookup failure block history logging — better an incomplete
    label than a dropped history document.
    """
    try:
        twin = get_twin(thing_id)
        name = twin.get("attributes", {}).get("name")
        return name if name else thing_id
    except Exception as e:
        print(f"history_service: could not resolve farm name for {thing_id}:", e)
        return thing_id


def save_raw_sensor_history(device_id, sensor_type, readings, thing_id):
    """
    Per-device raw snapshot — thing_id here is the physical sensor's own
    Ditto thing (smartfarm:s01 etc.), not a farm, so there is no farm
    name to attach. This is deliberately pre-mapping, pre-farm data.
    """
    document = {
        "timestamp": datetime.utcnow(),
        "thingId": thing_id,
        "deviceId": device_id,
        "sensorType": sensor_type,
        **{k: v for k, v in readings.items() if k not in ("sensorId", "sensorType")}
    }
    raw_sensor_history.insert_one(document)


def save_actual_sensor_history(data, thing_id):
    """Periodic full-feature snapshot of a farm's 'actual' (twin-processed)
    properties — readings after farm-mapping filtering and any off-channel
    simulation; this is the twin's actual output. Written every 30s by
    history_logger's loop, for every farm."""

    document = {
        "timestamp": datetime.utcnow(),
        "thingId": thing_id,
        "farmName": _farm_name_for(thing_id),
        **data
    }

    actual_sensor_history.insert_one(document)


def save_actual_override(
    property_name,
    before_state,
    after_state,
    thing_id
):
    """
    Discrete before/after edit event for one 'actual' property — fired
    by ditto_writer.update_actual_properties() every time someone PATCHes
    /farm/{id}/actual. One document per changed property, NOT a periodic
    snapshot (that's save_actual_sensor_history's job).
    """

    document = {
        "timestamp": datetime.utcnow(),
        "thingId": thing_id,
        "farmName": _farm_name_for(thing_id),
        "overrideProperty": property_name,
        "before": before_state,
        "after": after_state,
        "source": "dashboard"
    }

    actual_override_history.insert_one(document)


def save_virtual_change(
    property_name,
    before_state,
    after_state,
    thing_id
):
    """
    Discrete before/after edit event for one 'virtual' property — fired
    by ditto_writer.update_virtual_properties() every time someone PATCHes
    /farm/{id}/virtual. Deliberately separate from save_virtual_sensor_history
    (the periodic full snapshot) so a document is never ambiguous between
    "this is a full snapshot" and "this is a single-field diff".
    """

    document = {
        "timestamp": datetime.utcnow(),
        "thingId": thing_id,
        "farmName": _farm_name_for(thing_id),
        "changedProperty": property_name,
        "before": before_state,
        "after": after_state,
        "source": "dashboard"
    }

    virtual_history.insert_one(document)


def save_virtual_sensor_history(data, thing_id="smartfarm:twin01"):
    document = {
        "timestamp": datetime.utcnow(),
        "thingId": thing_id,
        "farmName": _farm_name_for(thing_id),
        **data
    }
    virtual_sensor_history.insert_one(document)