"""
Independent MQTT subscriber for sensor *discovery*.

This runs alongside (not instead of) Ditto's own "Smart Farm MQTT"
connection. Ditto's connection keeps doing exactly what it does today:
unit "1" -> smartfarm:twin01 actual feed (the legacy probe).

This listener subscribes to the same broker on a wildcard topic so it
also sees any *other* unit number you point a new ESP32 at (e.g.
"farm/soil/2", "farm/soil/3", ...). The unit number in the topic IS the
device id — no firmware payload changes are needed, just change the
`client.publish("farm/soil/<N>", ...)` line on the new unit to a number
other than 1.

Unit "1" is explicitly skipped here since it's already wired up.
"""

import json
import time
import paho.mqtt.client as mqtt

from app.sensor_registry import ingest_reading

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPIC_FILTER = "sensors/+/+"   # sensors/<type>/<deviceId>


def _device_id_from_topic(topic: str) -> str:
    return topic.rstrip("/").split("/")[-1]


def _on_connect(client, userdata, flags, rc):
    print("sensor_listener: connected to broker, rc =", rc)
    client.subscribe(TOPIC_FILTER)


def _on_message(client, userdata, msg):
    device_id = _device_id_from_topic(msg.topic)

    if not device_id or device_id == "undefined":
        return

    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except Exception as e:
        print("sensor_listener: bad payload on", msg.topic, e)
        return

    channels = {
        k: v for k, v in payload.items()
        if isinstance(v, (int, float))
        and k
        and k != "undefined"
    }
    if not channels:
        return

    try:
        ingest_reading(device_id, channels)
    except Exception as e:
        print("sensor_listener: ingest failed for unit", device_id, e)


def start_sensor_listener():
    client = mqtt.Client()
    client.on_connect = _on_connect
    client.on_message = _on_message

    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            client.loop_forever()
        except Exception as e:
            print("sensor_listener: connection failed, retrying in 5s:", e)
            time.sleep(5)