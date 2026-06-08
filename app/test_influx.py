from influxdb_client import InfluxDBClient
from app.config import settings

client = InfluxDBClient(
    url=settings.INFLUX_URL,
    token=settings.INFLUX_TOKEN,
    org=settings.INFLUX_ORG
)

print("CONNECTED")