

import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime

DITTO_BASE_URL = "http://localhost:8080/api/2/things"
CATALOG_THING_ID = "smartfarm:sensor_catalog"
CATALOG_POLICY_ID = "smartfarm:policy"
AUTH = HTTPBasicAuth("ditto", "ditto")
MERGE_HEADERS = {"Content-Type": "application/merge-patch+json"}


def ensure_catalog():
    """
    Create the catalog thing if it doesn't exist.

    Cheap to call defensively — every function below that writes into the
    catalog calls this first, since the only thing that genuinely has to
    pre-exist for a Ditto merge-patch to succeed is the THING itself, not
    each individual feature inside it. (Confirmed empirically: merging a
    brand-new feature key into an existing thing creates it in one call —
    JSON Merge Patch / RFC 7396 treats a missing target as {} and applies
    the patch on top of that. Only the parent thing needs to be real.)
    """
    res = requests.get(f"{DITTO_BASE_URL}/{CATALOG_THING_ID}", auth=AUTH)
    if res.status_code == 404:
        put_res = requests.put(
            f"{DITTO_BASE_URL}/{CATALOG_THING_ID}",
            auth=AUTH,
            json={
                "policyId": CATALOG_POLICY_ID,
                "attributes": {"type": "sensor_catalog"},
                "features": {}
            }
        )
        put_res.raise_for_status()
    elif res.status_code != 200:
        res.raise_for_status()


def _get_features() -> dict:
    res = requests.get(f"{DITTO_BASE_URL}/{CATALOG_THING_ID}/features", auth=AUTH)
    if res.status_code == 404:
        return {}
    res.raise_for_status()
    return res.json()


def _merge_feature(key: str, properties: dict):
    """Single choke point for every catalog write — guarantees the thing
    exists first, and raises loudly instead of failing silently."""
    ensure_catalog()
    res = requests.patch(
        f"{DITTO_BASE_URL}/{CATALOG_THING_ID}/features/{key}",
        auth=AUTH,
        json={"properties": properties},
        headers=MERGE_HEADERS
    )
    res.raise_for_status()


def _replace_feature_property(key: str, prop_path: str, value):
    """
    PUT (not merge-patch) a single property path on a catalog feature.

    Used for the 'mappings' list specifically — merge-patch can't remove
    an array element or shrink a list, it can only overlay objects. Since
    unmapping a farm means the mappings list must get SHORTER, a plain
    JSON merge can never express that. A direct PUT to the property path
    replaces it wholesale, which is what list semantics require.
    """
    ensure_catalog()
    res = requests.put(
        f"{DITTO_BASE_URL}/{CATALOG_THING_ID}/features/{key}/properties/{prop_path}",
        auth=AUTH,
        json=value
    )
    res.raise_for_status()


def _normalize_mappings(props: dict) -> list:
    """
    Read mappings off a catalog entry, transparently upgrading the old
    single-farmId shape if that's all that's there yet.

    Old shape:  {"farmId": "farm01"}
    New shape:  {"mappings": [{"farmId": "farm01", "channels": null}]}

    Never writes anything here — this is a read-time view only. The
    upgrade to the new shape on disk happens the first time map_sensor()
    is called for that sensor.
    """
    mappings = props.get("mappings")
    if isinstance(mappings, list):
        return mappings

    legacy_farm_id = props.get("farmId")
    if legacy_farm_id:
        return [{"farmId": legacy_farm_id, "channels": None}]

    return []


def seed_virtual_sensors(farm_thing_ids: list):
    """
    Scan each farm's virtual properties and register any key not yet in
    the catalog as a virtual sensor.

    DESIGN NOTE — this intentionally checks against the catalog globally,
    not per-farm. Virtual sensors (humidity, rainfall, ndvi...) are a
    shared library of metric TYPES, not per-farm instances — one catalog
    entry for "humidity" represents that metric type regardless of which
    farm first introduced it. This mirrors how real sensors work too:
    one catalog entry per physical device (e.g. "s01"), which can now be
    mapped to one or more farms via its 'mappings' list. Neither real nor
    virtual entries are duplicated per-farm — farm association lives in
    the mappings field, not in the catalog key itself.

    Safe to call on every startup — keys already present (real or
    virtual) are left untouched, so renames/mappings already made are
    never overwritten.
    """
    from app.ditto_reader import get_virtual

    ensure_catalog()
    features = _get_features()
    now = datetime.utcnow().isoformat()

    for thing_id in farm_thing_ids:
        try:
            virtual_props = get_virtual(thing_id)
        except Exception as e:
            # Logged, not swallowed — a genuine Ditto/network failure here
            # should be visible, not indistinguishable from "no virtual
            # feature on this farm yet" (which is also a valid, harmless case).
            print(f"seed_virtual_sensors: could not read virtual properties for {thing_id}: {e}")
            continue

        for key in virtual_props:
            if key in features:
                continue

            try:
                _merge_feature(key, {
                    "name": key,
                    "source": "virtual",
                    "deviceId": None,
                    "sensorType": None,
                    "channels": None,
                    "mappings": [],
                    "min": {},
                    "max": {},
                    "enabled": {},
                    "isNew": False,
                    "firstSeen": now,
                    "lastSeen": now
                })
                features[key] = {"properties": {}}
            except Exception as e:
                print(f"seed_virtual_sensors: could not register '{key}' from {thing_id}: {e}")


def get_all_sensors() -> list:
    """
    Return every sensor in the catalog.

    Real sensors are keyed by deviceId (e.g. "s01") and carry a
    'channels' list of the readings that device reports — set by the
    Ditto mapper on every MQTT publish.

    A feature missing a 'name' property hasn't been fully registered yet
    (the mapper only writes source/sensorType/channels/lastSeen) — finish
    that here: assign a default display name and flag it as newly
    discovered so the dashboard can highlight it.

    Each sensor's 'mappings' is a list of {farmId, channels} — channels
    null means "every channel this sensor reports", a list means "only
    these channels go to this farm". This lets one physical sensor feed
    several farms at once, with different farms seeing different subsets
    of its channels.
    """
    ensure_catalog()
    features = _get_features()
    now = datetime.utcnow().isoformat()
    sensors = []

    for key, feature in features.items():
        props = feature.get("properties", {})

        if "name" not in props:
            patch = {
                "name": key,
                "isNew": True,
                "firstSeen": props.get("lastSeen", now)
            }
            try:
                _merge_feature(key, patch)
                props.update(patch)
            except Exception as e:
                print(f"get_all_sensors: could not finish registering '{key}': {e}")
                # fall through and show it anyway with best-effort defaults
                props.setdefault("name", key)

        source = props.get("source", "virtual")
        channels = props.get("channels") or []

        sensors.append({
            "rawKey": key,
            "key": key,
            "name": props.get("name", key),
            "source": source,
            "deviceId": key if source == "real" else None,
            "sensorType": props.get("sensorType"),
            "channels": props.get("channels"),
            "mappings": _normalize_mappings(props),
            "min": props.get("min", {}),
            "max": props.get("max", {}),
            "enabled": props.get("enabled", {}),
            "isNew": props.get("isNew", False),
            "firstSeen": props.get("firstSeen"),
            "lastSeen": props.get("lastSeen"),
        })

    # real sensors first, then alphabetical within each group
    return sorted(sensors, key=lambda s: (s["source"] != "real", s["key"]))


def rename_sensor(key: str, new_name: str) -> dict:
    _merge_feature(key, {"name": new_name})
    return {"status": "success", "key": key, "name": new_name}


def get_sensor(key: str) -> dict:
    """Fetch a single catalog entry's raw properties. Returns {} if the
    sensor doesn't exist yet (callers should treat that as 'not found')."""
    ensure_catalog()
    res = requests.get(f"{DITTO_BASE_URL}/{CATALOG_THING_ID}/features/{key}/properties", auth=AUTH)
    if res.status_code == 404:
        return {}
    res.raise_for_status()
    return res.json()


def map_sensor_to_farms(key: str, mappings: list) -> dict:
    """
    Replace a sensor's full list of farm mappings.

    mappings: [{"farmId": "farm01", "channels": null}, {"farmId": "farm02", "channels": ["moisture"]}]
    Pass an empty list to unmap the sensor from everything.

    This REPLACES the whole list rather than merging — the caller (the
    API layer) is responsible for sending the complete desired set, since
    that's the only way to express "remove farm01" through a PATCH-style
    call without a separate delete endpoint per mapping.
    """
    clean = []
    for m in mappings or []:
        farm_id = m.get("farmId")
        if not farm_id:
            continue
        channels = m.get("channels")
        if channels is not None and not isinstance(channels, list):
            raise ValueError("channels must be a list or null")
        clean.append({"farmId": farm_id, "channels": channels})

    _replace_feature_property(key, "mappings", clean)
    # keep the legacy single-farmId field roughly in sync for any code
    # that hasn't been migrated yet — first mapping wins, null if none
    legacy_farm_id = clean[0]["farmId"] if clean else None
    _merge_feature(key, {"farmId": legacy_farm_id})

    return {"status": "success", "key": key, "mappings": clean}


def add_sensor_mapping(key: str, farm_id: str, channels=None) -> dict:
    """Add one farm mapping without disturbing existing ones — this is
    what lets the same sensor be added to a second farm."""
    if not farm_id:
        raise ValueError("farm_id is required")
    current = _normalize_mappings(get_sensor(key))

    # replace any existing mapping for this farm (re-mapping channels),
    # otherwise append a new one
    next_mappings = [m for m in current if m.get("farmId") != farm_id]
    next_mappings.append({"farmId": farm_id, "channels": channels})

    return map_sensor_to_farms(key, next_mappings)


def remove_sensor_mapping(key: str, farm_id: str) -> dict:
    """Remove just one farm mapping, leaving any others untouched."""
    current = _normalize_mappings(get_sensor(key))
    next_mappings = [m for m in current if m.get("farmId") != farm_id]
    return map_sensor_to_farms(key, next_mappings)


def map_sensor_to_farm(key: str, farm_id) -> dict:
    """
    Back-compat wrapper for the old single-farm API shape.

    farm_id=None clears every mapping (matches the old "unassign"
    behaviour). farm_id=<id> sets that as the ONLY mapping, replacing any
    others — call add_sensor_mapping() instead if you want to add a farm
    without removing existing ones.
    """
    if not farm_id:
        return map_sensor_to_farms(key, [])
    return map_sensor_to_farms(key, [{"farmId": farm_id, "channels": None}])


def set_channel_range(key: str, channel: str, min_value=None, max_value=None) -> dict:
    """
    Store min/max for one channel of a sensor, server-side, in the
    catalog. This is what makes a min/max edit survive a refresh and
    apply the same way for every viewer, instead of living only in one
    browser tab's memory.
    """
    current = get_sensor(key)
    mins = dict(current.get("min", {}))
    maxs = dict(current.get("max", {}))

    if min_value is not None:
        mins[channel] = min_value
    if max_value is not None:
        maxs[channel] = max_value

    _merge_feature(key, {"min": mins, "max": maxs})
    return {"status": "success", "key": key, "channel": channel, "min": mins.get(channel), "max": maxs.get(channel)}


def set_channel_enabled(key: str, channel: str, enabled: bool) -> dict:
    """
    Store the on/off state for one channel, server-side. This is what
    history_logger's sync loop checks before pushing a reading into any
    mapped farm — so 'off' actually stops data from moving, instead of
    just hiding it in one browser tab while the next 30s sync overwrites
    it with real data again.
    """
    current = get_sensor(key)
    enabled_map = dict(current.get("enabled", {}))
    enabled_map[channel] = bool(enabled)

    _merge_feature(key, {"enabled": enabled_map})
    return {"status": "success", "key": key, "channel": channel, "enabled": enabled_map[channel]}


def set_sensor_source(key: str, source: str) -> dict:
    """Flip a sensor between 'real' and 'virtual' — e.g. demoting a
    disconnected real sensor back to a simulated value, or vice versa."""
    if source not in ("real", "virtual"):
        raise ValueError("source must be 'real' or 'virtual'")
    _merge_feature(key, {"source": source})
    return {"status": "success", "key": key, "source": source}


def acknowledge_sensor(key: str) -> dict:
    _merge_feature(key, {"isNew": False})
    return {"status": "success", "key": key}


def unmap_sensors_for_farm(farm_id: str) -> dict:
    """
    Called when a farm is deleted — clears any mapping pointing at it on
    every catalog sensor, so the history sync loop never tries to write
    into a thing that no longer exists (the exact bug field01 caused: a
    sensor stayed mapped to a thing that was gone, and every 30s sync
    cycle hit a 404 trying to write to it).

    A sensor mapped to multiple farms only loses the mapping for the
    deleted farm — its other mappings are untouched.
    """
    ensure_catalog()
    features = _get_features()
    cleared = []

    for key, feature in features.items():
        props = feature.get("properties", {})
        current = _normalize_mappings(props)
        if any(m.get("farmId") == farm_id for m in current):
            try:
                remove_sensor_mapping(key, farm_id)
                cleared.append(key)
            except Exception as e:
                print(f"unmap_sensors_for_farm: could not clear '{key}': {e}")

    return {"status": "success", "clearedSensors": cleared}