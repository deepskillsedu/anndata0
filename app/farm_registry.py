import re
import requests
from requests.auth import HTTPBasicAuth

from app.ditto_writer import create_thing, delete_thing

DITTO_SEARCH_URL = "http://localhost:8080/api/2/search/things"
AUTH = HTTPBasicAuth("ditto", "ditto")

# Infrastructure things — never shown in the farm list
EXCLUDED_THING_IDS = {"smartfarm:sensor_registry"}

FARM_ID_PATTERN = re.compile(r"^smartfarm:farm(\d+)$")


def list_farm_thing_ids() -> list:
    """Return every smartfarm thing except infrastructure."""
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
    ]


def next_farm_id() -> str:
    used = []
    for thing_id in list_farm_thing_ids():
        match = FARM_ID_PATTERN.match(thing_id)
        if match:
            used.append(int(match.group(1)))
    next_number = (max(used) + 1) if used else 1
    return f"farm{next_number:02d}"


def create_farm(name: str, field: str = None, crop: str = None) -> dict:
    farm_id = next_farm_id()
    thing_id = f"smartfarm:{farm_id}"
    create_thing(thing_id, name, field, crop)
    return {"farm_id": farm_id, "thing_id": thing_id, "name": name}


def delete_farm(farm_id: str) -> dict:
    """Permanently deletes a farm's Ditto thing. farm_id is the short id
    (e.g. 'farm03' or 'twin01'), not the full 'smartfarm:farm03' thing id."""
    thing_id = farm_id if ":" in farm_id else f"smartfarm:{farm_id}"
    if thing_id in EXCLUDED_THING_IDS:
        raise ValueError("Cannot delete infrastructure thing")
    return delete_thing(thing_id)