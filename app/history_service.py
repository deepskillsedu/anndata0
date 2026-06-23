from datetime import datetime

from app.mongodb_service import (
    actual_sensor_history,
    actual_override_history,
    virtual_history,
    virtual_sensor_history,
    raw_sensor_history
)


def save_raw_sensor_history(device_id, sensor_type, readings, thing_id):
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
        "changedProperty": property_name,
        "before": before_state,
        "after": after_state,
        "source": "dashboard"
    }

    virtual_history.insert_one(document)


def save_virtual_sensor_history(data, thing_id):
    """
    Periodic full-feature snapshot of a farm's virtual properties — the
    direct counterpart to save_actual_sensor_history. Called from
    history_logger's loop on the same cadence as the actual snapshot.
    """

    document = {
        "timestamp": datetime.utcnow(),
        "thingId": thing_id,
        **data
    }

    virtual_sensor_history.insert_one(document)