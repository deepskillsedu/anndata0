import requests

DITTO_URL = "http://localhost:8080/api/2/things/smartfarm:field01"

AUTH = ("ditto", "ditto")


def update_ditto(sensor_data):

    payload = {
        "features": {
            "moisture": {
                "properties": {
                    "value": sensor_data["moisture"]
                }
            },
            "temperature": {
                "properties": {
                    "value": sensor_data["temperature"]
                }
            },
            "ph": {
                "properties": {
                    "value": sensor_data["ph"]
                }
            },
            "ec": {
                "properties": {
                    "value": sensor_data["ec"]
                }
            },
            "nitrogen": {
                "properties": {
                    "value": sensor_data["nitrogen"]
                }
            },
            "phosphorus": {
                "properties": {
                    "value": sensor_data["phosphorus"]
                }
            },
            "potassium": {
                "properties": {
                    "value": sensor_data["potassium"]
                }
            }
        }
    }

    requests.put(
        DITTO_URL,
        auth=AUTH,
        json=payload
    )