import random
import time
import requests

from app.ditto_reader import get_actual, get_virtual, get_twin, thing_id_for_farm, thing_exists
from app.ditto_writer import DITTO_BASE_URL, AUTH, MERGE_HEADERS
from app.farm_registry import list_farm_thing_ids
from app.sensor_registry import get_all_sensors, unmap_sensors_for_farm
from app.history_service import save_actual_sensor_history, save_virtual_sensor_history, save_raw_sensor_history


def _simulated_value(sensor: dict, channel: str):
    """
    Generate one fallback reading for a channel that's been administratively
    switched off, using the min/max range saved for it on the Sensors/Twin
    page. Defaults to 0-100 if no range was ever saved for this channel, so
    an old sensor with no saved range still gets *something* rather than
    erroring out mid-sync.
    """
    lo = (sensor.get("min") or {}).get(channel, 0)
    hi = (sensor.get("max") or {}).get(channel, 100)
    if lo > hi:
        lo, hi = hi, lo
    return round(random.uniform(lo, hi), 2)


def _apply_channel_filters(sensor: dict, readings: dict, mapping_channels) -> dict:
    """
    Narrow a device's raw readings down to what one specific farm mapping
    is actually allowed to receive, AND substitute a simulated value for
    any channel that's been switched off.

    mapping_channels: None means "every channel this sensor reports" for
    this mapping; a list means "only these channels go to this farm".

    A channel turned off (enabled[channel] is False) is off for EVERY
    mapping, regardless of that mapping's own channel subset — turning a
    channel off means "this channel is no longer live hardware data
    anywhere", not just "don't show it on one farm". Rather than dropping
    the key (which froze the farm's last real value forever), we now write
    a freshly random value each cycle within the saved min/max range, so
    Ditto keeps receiving a live-looking reading for it. The instant it's
    switched back on, the very next cycle resumes writing the real device
    reading instead — there is no separate "catch up" step needed.
    """
    enabled = sensor.get("enabled") or {}
    allowed = set(mapping_channels) if mapping_channels is not None else None
    result = {}

    channels_to_consider = allowed if allowed is not None else set(readings.keys()) | set(enabled.keys())
    channels_to_consider -= {"sensorId", "sensorType"}

    for k in channels_to_consider:
        if enabled.get(k) is False:
            result[k] = _simulated_value(sensor, k)
        elif k in readings:
            result[k] = readings[k]
        # else: channel is on but the device hasn't reported it yet — skip, nothing to send

    return result


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

        # Container #1: the EXACT reading off this device, untouched —
        # saved immediately, before _apply_channel_filters does any
        # enable/disable substitution or per-farm channel narrowing.
        # One document per device per sync cycle, regardless of how many
        # farms it's mapped to.
        if readings:
            try:
                save_raw_sensor_history(readings, device_thing_id)
            except Exception as e:
                print(f"history logger error (raw, {device_thing_id}):", e)

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

            clean_readings = _apply_channel_filters(s, readings, mapping.get("channels"))
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

        # 1. Bridge: push mapped real sensor readings into their farms
        sync_real_sensors_to_farms()

        # 2. Snapshot every farm's actual properties into Mongo history
        try:
            thing_ids = list_farm_thing_ids()
        except Exception as e:
            print("could not list farms:", e)
            thing_ids = []

        for thing_id in thing_ids:
            try:
                actual = get_actual(thing_id)
                save_actual_sensor_history(actual, thing_id=thing_id)
            except Exception as e:
                print(f"history logger error (actual, {thing_id}):", e)
 
            try:
                virtual = get_virtual(thing_id)
                save_virtual_sensor_history(virtual, thing_id=thing_id)
            except Exception as e:
                print(f"history logger error (virtual, {thing_id}):", e)
 
            print(f"history saved: {thing_id}")

        time.sleep(30)