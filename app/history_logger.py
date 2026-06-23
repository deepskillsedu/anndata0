import random
import time
import requests

from app.ditto_reader import get_actual, get_twin, thing_id_for_farm, thing_exists
from app.ditto_writer import DITTO_BASE_URL, AUTH, MERGE_HEADERS
from app.farm_registry import list_farm_thing_ids
from app.sensor_registry import get_all_sensors, unmap_sensors_for_farm
from app.history_service import save_actual_sensor_history, save_raw_sensor_history


def _effective_enabled(sensor: dict, mapping: dict, channel: str) -> bool:
    """
    A channel's effective on/off state for ONE specific farm mapping.

    Checks that mapping's own "enabled" override first; only if it has
    none for this channel does it fall back to the sensor-wide default.
    This is the core of the per-farm fix: two farms mapped to the same
    sensor can now disagree about whether a channel is on, because each
    farm's mapping carries its own answer instead of all of them sharing
    one sensor-level flag.
    """
    mapping_value = (mapping.get("enabled") or {}).get(channel)
    if mapping_value is not None:
        return mapping_value
    return (sensor.get("enabled") or {}).get(channel, True)


def _effective_range(sensor: dict, mapping: dict, channel: str):
    """
    A channel's effective (min, max) for ONE specific farm mapping.

    Same precedence as _effective_enabled: that mapping's own "ranges"
    override first, sensor-wide default second, 0-100 last resort. This
    is what lets the same sensor's channel — e.g. boron — be 10-23 on
    one farm and 30-47 on another, instead of one shared range leaking
    across every farm it's mapped to.
    """
    mapping_range = (mapping.get("ranges") or {}).get(channel)
    if mapping_range and (mapping_range.get("min") is not None or mapping_range.get("max") is not None):
        lo = mapping_range.get("min", 0)
        hi = mapping_range.get("max", 100)
    else:
        lo = (sensor.get("min") or {}).get(channel, 0)
        hi = (sensor.get("max") or {}).get(channel, 100)
    if lo > hi:
        lo, hi = hi, lo
    return lo, hi


def _simulated_value(sensor: dict, mapping: dict, channel: str):
    """
    Generate one fallback reading for a channel that's off FOR THIS FARM,
    using whichever range is effective for this specific mapping (its own
    override if it has one, otherwise the sensor-wide default). Defaults
    to 0-100 if neither was ever saved, so an old sensor with no saved
    range still gets *something* rather than erroring out mid-sync.
    """
    lo, hi = _effective_range(sensor, mapping, channel)
    return round(random.uniform(lo, hi), 2)


def _apply_channel_filters(sensor: dict, mapping: dict, readings: dict) -> dict:
    """
    Narrow a device's raw readings down to what one specific farm mapping
    is actually allowed to receive, AND substitute a simulated value for
    any channel that's off FOR THIS FARM SPECIFICALLY.

    mapping["channels"]: None means "every channel this sensor reports"
    for this mapping; a list means "only these channels go to this farm".

    A channel's on/off state and simulated range are both resolved via
    _effective_enabled/_effective_range above — this mapping's own
    override if it has one, the sensor-wide default otherwise. That is
    the actual fix for "switching a sensor off on one farm switches it
    off everywhere": the decision is made per-mapping now, not from one
    shared sensor-level flag every farm used to read from identically.
    """
    mapping_channels = mapping.get("channels")
    allowed = set(mapping_channels) if mapping_channels is not None else None

    sensor_enabled_keys = set((sensor.get("enabled") or {}).keys())
    mapping_enabled_keys = set((mapping.get("enabled") or {}).keys())
    result = {}

    channels_to_consider = allowed if allowed is not None else (
        set(readings.keys()) | sensor_enabled_keys | mapping_enabled_keys
    )
    channels_to_consider -= {"sensorId", "sensorType"}

    for k in channels_to_consider:
        if not _effective_enabled(sensor, mapping, k):
            result[k] = _simulated_value(sensor, mapping, k)
        elif k in readings:
            result[k] = readings[k]
        # else: channel is on but the device hasn't reported it yet — skip, nothing to send

    return result


def snapshot_raw_sensor_data():
    """
    Container 1: snapshot exactly what every real sensor's OWN Ditto thing
    currently holds — no farm mapping, no channel subsetting, no off-channel
    simulation. Runs for every real catalog entry regardless of whether it
    has any farm mappings at all, because this answers "what did the sensor
    say" independent of "where is that data being used".

    Deliberately separate from sync_real_sensors_to_farms(): that function
    only looks at sensors with at least one mapping (it has nothing to do
    otherwise), which would silently skip a freshly-installed, not-yet-mapped
    sensor here too if the two were combined into one loop.
    """
    try:
        sensors = get_all_sensors()
    except Exception as e:
        print("raw snapshot: could not read sensor catalog:", e)
        return

    for s in sensors:
        if s["source"] != "real":
            continue

        device_id = s["deviceId"] or s["key"]
        sensor_type = s.get("sensorType")
        if not sensor_type:
            continue

        device_thing_id = f"smartfarm:{device_id}"
        try:
            twin = get_twin(device_thing_id)
        except Exception as e:
            print(f"raw snapshot: could not read device {device_thing_id}:", e)
            continue

        feature = twin.get("features", {}).get(sensor_type, {})
        readings = feature.get("properties", {}).get("readings", {})
        if not readings:
            continue  # device thing exists but has never published anything yet

        try:
            save_raw_sensor_history(device_id, sensor_type, readings, device_thing_id)
        except Exception as e:
            print(f"raw snapshot: could not save history for {device_thing_id}:", e)


def sync_real_sensors_to_farms():
    """
    The bridge: for every real sensor with at least one farm mapping,
    pull its latest reading off the device thing (smartfarm:s01 etc.)
    and merge it into EVERY farm it's mapped to — this is what makes the
    Twin tab show live hardware data once a sensor has been mapped on
    the Sensors page.

    A sensor can have several mappings at once (one physical device
    feeding multiple farms), and each mapping can carry its own channel
    subset — e.g. all 7 channels go to farm01, but only moisture also
    goes to farm02. A channel switched off via the Sensors/Twin page is
    replaced with a simulated value (random within its saved min/max)
    for every farm it's mapped to, instead of being frozen at its last
    real reading — see _apply_channel_filters above.

    Sensors with no mappings at all are skipped entirely.
    """
    try:
        sensors = get_all_sensors()
    except Exception as e:
        print("sync: could not read sensor catalog:", e)
        return

    for s in sensors:
        if s["source"] != "real" or not s.get("mappings"):
            continue

        device_id = s["deviceId"] or s["key"]
        device_thing_id = f"smartfarm:{device_id}"
        sensor_type = s.get("sensorType")
        if not sensor_type:
            continue

        try:
            twin = get_twin(device_thing_id)
        except Exception as e:
            print(f"sync: could not read device {device_thing_id}:", e)
            continue

        feature = twin.get("features", {}).get(sensor_type, {})
        readings = feature.get("properties", {}).get("readings", {})

        # NOTE: previously this skipped the whole sensor if the device had
        # never reported anything (`if not readings: continue`). That also
        # accidentally skipped channels that are switched OFF and only need
        # a simulated value — a brand-new device with zero real readings
        # yet should still be able to show simulated data for an off
        # channel. We only continue past here if there are genuinely no
        # readings AND no enabled-map entries to simulate from.
        if not readings and not (s.get("enabled") or {}):
            continue

        for mapping in s["mappings"]:
            farm_id = mapping.get("farmId")
            if not farm_id:
                continue

            clean_readings = _apply_channel_filters(s, mapping, readings)
            if not clean_readings:
                continue

            farm_thing_id = thing_id_for_farm(farm_id)

            # defensive: if the mapped farm no longer exists in Ditto (e.g.
            # it was deleted before the unmap step ran), clear the stale
            # mapping instead of retrying a write that will 404 forever.
            if not thing_exists(farm_thing_id):
                print(f"sync: farm {farm_thing_id} no longer exists — clearing stale mapping for {device_id}")
                try:
                    unmap_sensors_for_farm(farm_id)
                except Exception as e:
                    print(f"sync: could not clear stale mapping for {farm_id}:", e)
                continue

            try:
                response = requests.patch(
                    f"{DITTO_BASE_URL}/{farm_thing_id}/features/actual/properties",
                    auth=AUTH,
                    json=clean_readings,
                    headers=MERGE_HEADERS
                )
                response.raise_for_status()
            except Exception as e:
                print(f"sync: could not write farm {farm_thing_id}:", e)


def start_history_logger():

    while True:

        # 1. Container 1: snapshot every real sensor's exact own data,
        #    independent of farm mapping entirely.
        snapshot_raw_sensor_data()

        # 2. Bridge: push mapped real sensor readings into their farms
        sync_real_sensors_to_farms()

        # 3. Container 2: snapshot every farm's actual properties (post-twin,
        #    post-mapping, post-filtering) into Mongo history.
        try:
            thing_ids = list_farm_thing_ids()
        except Exception as e:
            print("could not list farms:", e)
            thing_ids = []

        for thing_id in thing_ids:
            try:
                actual = get_actual(thing_id)
                save_actual_sensor_history(actual, thing_id=thing_id)
                print(f"history saved: {thing_id}")
            except Exception as e:
                print(f"history logger error ({thing_id}):", e)

        time.sleep(30)