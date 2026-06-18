import re
import requests
from requests.auth import HTTPBasicAuth

from app.ditto_writer import create_thing

DITTO_SEARCH_URL = "http://localhost:8080/api/2/search/things"
AUTH = HTTPBasicAuth("ditto", "ditto")

FARM_ID_PATTERN = re.compile(r"^smartfarm:farm(\d+)$")


def list_farm_thing_ids():
    response = requests.get(
        DITTO_SEARCH_URL,
        auth=AUTH,
        params={"filter": 'eq(attributes/type,"farm")'},
    )
    response.raise_for_status()
    return [item["thingId"] for item in response.json().get("items", [])]


def next_farm_id() -> str:
    used = []
    for thing_id in list_farm_thing_ids():
        match = FARM_ID_PATTERN.match(thing_id)
        if match:
            used.append(int(match.group(1)))
    next_number = (max(used) + 1) if used else 1
    return f"farm{next_number:02d}"


def create_farm(name: str, field: str = None, crop: str = None):
    farm_id = next_farm_id()
    thing_id = f"smartfarm:{farm_id}"
    create_thing(thing_id, name, field, crop)
    return {"farm_id": farm_id, "thing_id": thing_id, "name": name}