"""
sensor_router.py

Closes the loop between sensor discovery and farm data.

The Ditto MQTT connection's mapping script (generic, never edited again)
writes every incoming sensor reading into smartfarm:sensor_registry,
under a feature named after the raw MQTT topic segment (e.g.
'sensor_1' for farm/soil/1), as {"data": {...}, "lastSeen": ...}.

This module runs as a background loop: for every registered sensor that
HAS a farmId mapped (set by the user from the dashboard via
map_sensor_to_farm), it takes that sensor's latest 'data' and PATCHes it
into the target farm's real features/actual/properties. Sensors with no
farmId mapped yet are left alone — their data sits in the registry,
visible to the dashboard as "unmapped", until the user assigns them.

This is the only piece that writes into a farm's actual.properties from
live hardware. actual_simulator.py is the parallel path for sensors a
user has explicitly turned OFF (no trust in live data) — the two never
target the same sensor at the same time, enforced by sensor mode.
"""

import time

from app.sensor_registry import get_all_sensors
from app.ditto_writer import update_actual_properties
from app.ditto_reader import thing_id_for_farm

# Tracks lastSeen per sensorId so we only forward genuinely new readings,
# not re-push the same value every loop tick.
_last_forwarded = {}


def tick_once():
    sensors = get_all_sensors()

    # group by farm so multiple sensors mapped to the same farm in one
    # tick result in a single PATCH per farm, not one per sensor
    by_farm = {}

    for sensor in sensors:
        farm_id = sensor.get("farmId")
        data = sensor.get("data") or {}
        last_seen = sensor.get("lastSeen")

        if not farm_id or not data:
            continue  # unmapped, or no reading received yet

        sensor_key = sensor["rawKey"]
        if _last_forwarded.get(sensor_key) == last_seen:
            continue  # already forwarded this exact reading

        by_farm.setdefault(farm_id, {}).update(data)
        _last_forwarded[sensor_key] = last_seen

    for farm_id, properties in by_farm.items():
        try:
            update_actual_properties(properties, thing_id=thing_id_for_farm(farm_id))
        except Exception as e:
            print(f"sensor_router error forwarding to {farm_id}:", e)


def start_sensor_router(interval_seconds: int = 5):
    while True:
        try:
            tick_once()
        except Exception as e:
            print("sensor_router loop error:", e)
        time.sleep(interval_seconds)