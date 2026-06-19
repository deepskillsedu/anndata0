# import requests
# from requests.auth import HTTPBasicAuth

# from app.history_service import (
#     save_virtual_change,
#     save_actual_override
# )

# from app.ditto_reader import (
#     get_virtual,
#     get_actual
# )

# DITTO_BASE_URL = "http://localhost:8080/api/2/things"
# THING_ID = "smartfarm:twin01"

# AUTH = HTTPBasicAuth(
#     "ditto",
#     "ditto"
# )


# def update_virtual_property(name, value):

#     current_virtual = get_virtual()

#     old_value = current_virtual.get(name)

#     response = requests.put(
#         f"{DITTO_BASE_URL}/{THING_ID}/features/virtual/properties/{name}",
#         auth=AUTH,
#         json=value
#     )

#     response.raise_for_status()

#     save_virtual_change(
#         name,
#         old_value,
#         value
#     )

#     return {
#         "status": "success",
#         "property": name,
#         "oldValue": old_value,
#         "value": value
#     }


# def update_actual_property(name, value):

#     current_actual = get_actual()

#     old_value = current_actual.get(name)

#     response = requests.put(
#         f"{DITTO_BASE_URL}/{THING_ID}/features/actual/properties/{name}",
#         auth=AUTH,
#         json=value
#     )

#     response.raise_for_status()

#     save_actual_override(
#         name,
#         old_value,
#         value
#     )

#     return {
#         "status": "success",
#         "property": name,
#         "oldValue": old_value,
#         "value": value
#     }



# import requests
# from requests.auth import HTTPBasicAuth

# from app.history_service import (
#     save_virtual_change,
#     save_actual_override
# )

# from app.ditto_reader import (
#     get_virtual,
#     get_actual
# )

# DITTO_BASE_URL = "http://localhost:8080/api/2/things"
# THING_ID = "smartfarm:twin01"

# AUTH = HTTPBasicAuth(
#     "ditto",
#     "ditto"
# )


# def update_virtual_property(name, value):

#     current_virtual = get_virtual()

#     old_value = current_virtual.get(name)

#     response = requests.put(
#         f"{DITTO_BASE_URL}/{THING_ID}/features/virtual/properties/{name}",
#         auth=AUTH,
#         json=value
#     )

#     response.raise_for_status()

#     save_virtual_change(
#         name,
#         old_value,
#         value
#     )

#     return {
#         "status": "success",
#         "property": name,
#         "oldValue": old_value,
#         "value": value
#     }


# def update_actual_property(name, value):

#     current_actual = get_actual()

#     old_value = current_actual.get(name)

#     response = requests.put(
#         f"{DITTO_BASE_URL}/{THING_ID}/features/actual/properties/{name}",
#         auth=AUTH,
#         json=value
#     )

#     response.raise_for_status()

#     save_actual_override(
#         name,
#         old_value,
#         value
#     )

#     return {
#         "status": "success",
#         "property": name,
#         "oldValue": old_value,
#         "value": value
#     }




import requests
from requests.auth import HTTPBasicAuth

from app.history_service import save_virtual_change, save_actual_override
from app.ditto_reader import LEGACY_THING_ID, get_virtual, get_actual, thing_exists

DITTO_BASE_URL = "http://localhost:8080/api/2/things"
AUTH = HTTPBasicAuth("ditto", "ditto")
MERGE_HEADERS = {"Content-Type": "application/merge-patch+json"}


def create_thing(thing_id: str, name: str, field: str = None, crop: str = None):

    payload = {
        "attributes": {
            "type": "farm",
            "name": name,
            "field": field,
            "crop": crop
        },
        "features": {
            "actual": {"properties": {}},
            "simulatedActual": {"properties": {}},
            "virtual": {"properties": {}}
        }
    }

    response = requests.put(
        f"{DITTO_BASE_URL}/{thing_id}",
        auth=AUTH,
        json=payload
    )

    response.raise_for_status()

    return response.json()


def delete_thing(thing_id: str):
    """Permanently removes a farm's thing from Ditto. Used by DELETE
    /farms/{farm_id} so 'Remove' in the dashboard actually deletes the
    farm instead of just hiding it client-side (which used to make it
    reappear on the next refresh)."""

    response = requests.delete(
        f"{DITTO_BASE_URL}/{thing_id}",
        auth=AUTH
    )

    if response.status_code == 404:
        # already gone — treat as success, nothing left to do
        return {"status": "success", "thing_id": thing_id, "note": "already absent"}

    response.raise_for_status()

    return {"status": "success", "thing_id": thing_id}


def ensure_thing(thing_id: str, name: str = None, field: str = None, crop: str = None):
    """
    Auto-provisions the Ditto thing the first time a farm_id shows up,
    since the dashboard never calls an explicit create-farm route.
    """
    if not thing_exists(thing_id):
        create_thing(thing_id, name or thing_id, field, crop)


def update_virtual_properties(properties: dict, thing_id: str = LEGACY_THING_ID):

    ensure_thing(thing_id)

    current = get_virtual(thing_id)

    response = requests.patch(
        f"{DITTO_BASE_URL}/{thing_id}/features/virtual/properties",
        auth=AUTH,
        json=properties,
        headers=MERGE_HEADERS
    )

    response.raise_for_status()

    changes = {}

    for name, value in properties.items():
        old_value = current.get(name)
        save_virtual_change(name, old_value, value, thing_id=thing_id)
        changes[name] = {"oldValue": old_value, "value": value}

    return {
        "status": "success",
        "changes": changes
    }


def update_actual_properties(properties: dict, thing_id: str = LEGACY_THING_ID):

    ensure_thing(thing_id)

    current = get_actual(thing_id)

    response = requests.patch(
        f"{DITTO_BASE_URL}/{thing_id}/features/actual/properties",
        auth=AUTH,
        json=properties,
        headers=MERGE_HEADERS
    )

    response.raise_for_status()

    changes = {}

    for name, value in properties.items():
        old_value = current.get(name)
        save_actual_override(name, old_value, value, thing_id=thing_id)
        changes[name] = {"oldValue": old_value, "value": value}

    return {
        "status": "success",
        "changes": changes
    }


def update_simulated_actual_properties(properties: dict, thing_id: str = LEGACY_THING_ID):
    """Writes into the SEPARATE simulatedActual container — used for any
    sensor currently toggled OFF. Never touches the real 'actual' feature,
    so genuinely-real sensor history stays uncontaminated."""

    ensure_thing(thing_id)

    response = requests.patch(
        f"{DITTO_BASE_URL}/{thing_id}/features/simulatedActual/properties",
        auth=AUTH,
        json=properties,
        headers=MERGE_HEADERS
    )

    response.raise_for_status()

    return {
        "status": "success",
        "thing_id": thing_id,
        "properties": properties
    }