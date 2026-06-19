import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime

DITTO_BASE_URL = "http://localhost:8080/api/2/things"
REGISTRY_THING_ID = "smartfarm:sensor_registry"
AUTH = HTTPBasicAuth("ditto", "ditto")
MERGE_HEADERS = {"Content-Type": "application/merge-patch+json"}

SENSOR_ID_START = 100


def ensure_registry():
    """Create the registry thing in Ditto if it doesn't exist yet.
    Called once at FastAPI startup so the Ditto mapper can merge into it."""
    res = requests.get(f"{DITTO_BASE_URL}/{REGISTRY_THING_ID}", auth=AUTH)
    if res.status_code == 404:
        requests.put(
            f"{DITTO_BASE_URL}/{REGISTRY_THING_ID}",
            auth=AUTH,
            json={
                "attributes": {"type": "sensor_registry"},
                "features": {}
            }
        ).raise_for_status()


def _get_features() -> dict:
    res = requests.get(
        f"{DITTO_BASE_URL}/{REGISTRY_THING_ID}/features",
        auth=AUTH
    )
    if res.status_code == 404:
        return {}
    res.raise_for_status()
    return res.json()


def _next_sensor_id(features: dict) -> str:
    """Find the next available sXXX ID from the current features dict."""
    used = []
    for feature in features.values():
        sid = feature.get("properties", {}).get("sensorId", "")
        if sid.startswith("s"):
            try:
                used.append(int(sid[1:]))
            except ValueError:
                pass
    return f"s{(max(used) + 1) if used else SENSOR_ID_START}"


def get_all_sensors() -> list:
    """
    Return all sensors from the registry.
    Any feature discovered by the Ditto mapper (rawKey present, sensorId absent)
    gets a new sXXX ID assigned and written back to Ditto on this call.
    """
    ensure_registry()
    features = _get_features()
    sensors = []

    for raw_key, feature in features.items():
        props = feature.get("properties", {})
        sensor_id = props.get("sensorId")

        if not sensor_id:
            # Newly discovered by the Ditto MQTT mapper — assign an ID now
            sensor_id = _next_sensor_id(features)
            now = datetime.utcnow().isoformat()
            patch = {
                "sensorId": sensor_id,
                "rawKey": raw_key,
                "name": props.get("name", raw_key),
                "isNew": True,
                "firstSeen": props.get("firstSeen", now),
            }
            requests.patch(
                f"{DITTO_BASE_URL}/{REGISTRY_THING_ID}/features/{raw_key}/properties",
                auth=AUTH,
                json=patch,
                headers=MERGE_HEADERS
            )
            # Update local dict so subsequent iterations see this ID
            if "properties" not in features[raw_key]:
                features[raw_key]["properties"] = {}
            features[raw_key]["properties"].update(patch)
            props = features[raw_key]["properties"]

        sensors.append({
            "sensorId": sensor_id,
            "rawKey": raw_key,
            "name": props.get("name", raw_key),
            "farmId": props.get("farmId"),
            "firstSeen": props.get("firstSeen"),
            "lastSeen": props.get("lastSeen"),
            "isNew": props.get("isNew", False),
            "data": props.get("data", {}),
        })

    return sorted(sensors, key=lambda x: x["sensorId"])


def rename_sensor(raw_key: str, new_name: str) -> dict:
    res = requests.patch(
        f"{DITTO_BASE_URL}/{REGISTRY_THING_ID}/features/{raw_key}/properties",
        auth=AUTH,
        json={"name": new_name},
        headers=MERGE_HEADERS
    )
    res.raise_for_status()
    return {"status": "success", "rawKey": raw_key, "name": new_name}


def map_sensor_to_farm(raw_key: str, farm_id) -> dict:
    res = requests.patch(
        f"{DITTO_BASE_URL}/{REGISTRY_THING_ID}/features/{raw_key}/properties",
        auth=AUTH,
        json={"farmId": farm_id},
        headers=MERGE_HEADERS
    )
    res.raise_for_status()
    return {"status": "success", "rawKey": raw_key, "farmId": farm_id}


def acknowledge_sensor(raw_key: str) -> dict:
    """Clear the isNew flag once the user has seen the new sensor."""
    res = requests.patch(
        f"{DITTO_BASE_URL}/{REGISTRY_THING_ID}/features/{raw_key}/properties",
        auth=AUTH,
        json={"isNew": False},
        headers=MERGE_HEADERS
    )
    res.raise_for_status()
    return {"status": "success", "rawKey": raw_key}
