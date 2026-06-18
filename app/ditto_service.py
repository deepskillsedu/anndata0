# import requests

# FIELD_URL = "http://localhost:8080/api/2/things/smartfarm:field01"

# TWIN_ACTUAL_URL = (
#     "http://localhost:8080/api/2/things/"
#     "smartfarm:twin01/features/actual/properties"
# )

# AUTH = ("ditto", "ditto")


# def update_ditto(sensor_data):

# #real sensor twin

#     field_payload = {
#         "features": {
#             "moisture": {
#                 "properties": {
#                     "value": sensor_data["moisture"]
#                 }
#             },
#             "temperature": {
#                 "properties": {
#                     "value": sensor_data["temperature"]
#                 }
#             },
#             "ph": {
#                 "properties": {
#                     "value": sensor_data["ph"]
#                 }
#             },
#             "ec": {
#                 "properties": {
#                     "value": sensor_data["ec"]
#                 }
#             },
#             "nitrogen": {
#                 "properties": {
#                     "value": sensor_data["nitrogen"]
#                 }
#             },
#             "phosphorus": {
#                 "properties": {
#                     "value": sensor_data["phosphorus"]
#                 }
#             },
#             "potassium": {
#                 "properties": {
#                     "value": sensor_data["potassium"]
#                 }
#             }
#         }
#     }

#     requests.put(
#         FIELD_URL,
#         auth=AUTH,
#         json=field_payload
#     )

# # digital twin actual data

#     actual_payload = {
#         "moisture": sensor_data["moisture"],
#         "temperature": sensor_data["temperature"],
#         "ph": sensor_data["ph"],
#         "ec": sensor_data["ec"],
#         "nitrogen": sensor_data["nitrogen"],
#         "phosphorus": sensor_data["phosphorus"],
#         "potassium": sensor_data["potassium"]
#     }

#     requests.put(
#         TWIN_ACTUAL_URL,
#         auth=AUTH,
#         json=actual_payload
#     )




import requests
from requests.auth import HTTPBasicAuth

DITTO_BASE_URL = "http://localhost:8080/api/2/things"
AUTH = HTTPBasicAuth("ditto", "ditto")
MERGE_HEADERS = {"Content-Type": "application/merge-patch+json"}


def update_ditto(sensor_data: dict, farm_id: str = "twin01"):
    """sensor_data can contain any keys — adding a sensor on the ESP32/
    Modbus side just means a new key shows up here, no code change needed."""
    thing_id = f"smartfarm:{farm_id}"

    requests.patch(
        f"{DITTO_BASE_URL}/{thing_id}/features/actual/properties",
        auth=AUTH, json=sensor_data, headers=MERGE_HEADERS,
    )