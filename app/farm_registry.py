import re
import time
import requests
from requests.auth import HTTPBasicAuth

from app.ditto_writer import create_thing

DITTO_SEARCH_URL = "http://localhost:8080/api/2/search/things"
AUTH = HTTPBasicAuth("ditto", "ditto")

# Infrastructure things — never shown in the farm list
EXCLUDED_THING_IDS = {"smartfarm:sensor_catalog", "smartfarm:field01"}

# Physical sensor devices look like smartfarm:s01, smartfarm:s02 ...
SENSOR_PATTERN = re.compile(r"^smartfarm:s\d+$")

# Farm naming: farm_<YYYYMMDDHHMMSS>, e.g. farm_20260623091500
# Timestamp of creation moment (local time), not sequential and not
# derived from the typed name — so it carries no confusing "why is this
# farm04" meaning, and as a bonus tells you at a glance when a farm was
# created just by reading the ID.
FARM_ID_PATTERN = re.compile(r"^smartfarm:farm_(\d{14})$")

_MAX_GENERATION_ATTEMPTS = 10


def _timestamp_suffix() -> str:
    return time.strftime("%Y%m%d%H%M%S")


def list_farm_thing_ids() -> list:
    """Return every smartfarm thing that is a farm — excludes sensor
    devices (smartfarm:sXX) and infrastructure things (sensor_catalog)."""
    response = requests.get(
        DITTO_SEARCH_URL,
        auth=AUTH,
        params={
            "filter": 'like(thingId,"smartfarm:*")',
            "fields": "thingId",
            "option": "size(200)"
        }
    )
    response.raise_for_status()
    return [
        item["thingId"]
        for item in response.json().get("items", [])
        if item["thingId"] not in EXCLUDED_THING_IDS
        and not SENSOR_PATTERN.match(item["thingId"])
    ]


def list_sensor_thing_ids() -> list:
    """Return only physical sensor device things (smartfarm:s01, s02 ...)."""
    response = requests.get(
        DITTO_SEARCH_URL,
        auth=AUTH,
        params={
            "filter": 'like(thingId,"smartfarm:s*")',
            "fields": "thingId",
            "option": "size(200)"
        }
    )
    response.raise_for_status()
    return [
        item["thingId"]
        for item in response.json().get("items", [])
        if SENSOR_PATTERN.match(item["thingId"])
    ]


def next_farm_id() -> str:
    """
    Generate a fresh, unique farm ID from the current timestamp — e.g.
    farm_20260623091500.

    Not derived from the farm name (see chat history for why: renames,
    duplicate names, special characters all make slugified IDs messy)
    and not sequential (no more farm01/farm02/farm03 — those numbers
    carried no real meaning and got confusing once farms were deleted,
    leaving gaps). Collision-checked against existing thingIds; on the
    rare case two farms are created within the same second, this waits
    a second and retries rather than ever returning a colliding ID.
    """
    existing = set(list_farm_thing_ids())
    for attempt in range(_MAX_GENERATION_ATTEMPTS):
        candidate = f"farm_{_timestamp_suffix()}"
        thing_id = f"smartfarm:{candidate}"
        if thing_id not in existing:
            return candidate
        time.sleep(1)
    raise RuntimeError("Could not generate a unique farm ID after several attempts")


def create_farm(name: str, field: str = None, crop: str = None) -> dict:
    farm_id = next_farm_id()
    thing_id = f"smartfarm:{farm_id}"
    create_thing(thing_id, name, field, crop)
    return {"farm_id": farm_id, "thing_id": thing_id, "name": name}


def delete_farm(farm_id: str) -> dict:
    """
    Delete the farm's Ditto thing AND its policy, and clear any sensor
    mappings pointing at it, so nothing is left dangling like field01
    was.

    Uses ditto_writer.delete_thing() rather than a raw requests.delete
    here, specifically because that function also deletes the POLICY at
    /api/2/policies/{thing_id} — deleting only the thing (as this used
    to do) leaves an orphaned policy behind. That orphan is harmless on
    its own, but it's also exactly the kind of leftover state that made
    field01 a problem before, so we clean it up the same way thing
    deletion already does.
    """
    from app.sensor_registry import unmap_sensors_for_farm
    from app.ditto_writer import delete_thing

    thing_id = f"smartfarm:{farm_id}"

    delete_thing(thing_id)

    unmap_result = unmap_sensors_for_farm(farm_id)

    return {
        "status": "success",
        "deleted": thing_id,
        "clearedSensors": unmap_result.get("clearedSensors", [])
    }