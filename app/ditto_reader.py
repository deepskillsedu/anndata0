# import requests
# from requests.auth import HTTPBasicAuth

# DITTO_BASE_URL = "http://localhost:8080/api/2/things"
# THING_ID = "smartfarm:twin01"

# AUTH = HTTPBasicAuth(
#     "ditto",
#     "ditto"
# )


# def get_twin():
#     """
#     Return complete twin01 object.
#     """
#     response = requests.get(
#         f"{DITTO_BASE_URL}/{THING_ID}",
#         auth=AUTH
#     )

#     response.raise_for_status()

#     return response.json()


# def get_twin(thing_id):
#     response = requests.get(
#         f"{DITTO_BASE_URL}/{thing_id}",
#         auth=AUTH
#     )

#     response.raise_for_status()

#     return response.json()


# def get_actual():
#     """
#     Return actual sensor values.
#     """
#     twin = get_twin()
#     return twin["features"]["actual"]["properties"]


# def get_virtual():
#     """
#     Return virtual sensor values.
#     """
#     twin = get_twin()
#     return twin["features"]["virtual"]["properties"]


# def get_attributes():
#     """
#     Return farm metadata.
#     """
#     twin = get_twin()
#     return twin["attributes"]



import requests
from requests.auth import HTTPBasicAuth

DITTO_BASE_URL = "http://localhost:8080/api/2/things"
LEGACY_THING_ID = "smartfarm:twin01"

AUTH = HTTPBasicAuth("ditto", "ditto")


def thing_id_for_farm(farm_id: str) -> str:
    if not farm_id or farm_id == "legacy":
        return LEGACY_THING_ID
    return f"smartfarm:{farm_id}"


def thing_exists(thing_id: str) -> bool:
    response = requests.get(f"{DITTO_BASE_URL}/{thing_id}", auth=AUTH)
    return response.status_code == 200


def get_twin(thing_id: str = LEGACY_THING_ID):
    response = requests.get(f"{DITTO_BASE_URL}/{thing_id}", auth=AUTH)
    response.raise_for_status()
    return response.json()


def get_actual(thing_id: str = LEGACY_THING_ID):
    return get_twin(thing_id).get("features", {}).get("actual", {}).get("properties", {})


def get_virtual(thing_id: str = LEGACY_THING_ID):
    return get_twin(thing_id).get("features", {}).get("virtual", {}).get("properties", {})


def get_attributes(thing_id: str = LEGACY_THING_ID):
    return get_twin(thing_id).get("attributes", {})