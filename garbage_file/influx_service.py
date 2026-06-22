from influxdb_client import InfluxDBClient
from garbage_file.config import settings

client = InfluxDBClient(
    url=settings.INFLUX_URL,
    token=settings.INFLUX_TOKEN,
    org=settings.INFLUX_ORG
)

query_api = client.query_api()


def get_latest_data():
    query = f'''
    from(bucket: "{settings.INFLUX_BUCKET}")
      |> range(start: -1h)
      |> last()
    '''

    tables = query_api.query(query)

    data = {}

    for table in tables:
        for record in table.records:
            data[record["_field"]] = record["_value"]

    return data

def get_moisture_history():

    print("QUERY EXECUTED")

    query = f'''
    from(bucket: "{settings.INFLUX_BUCKET}")
      |> range(start: -30m)
      |> filter(fn: (r) => r["_field"] == "moisture")
      |> sort(columns: ["_time"])
    '''

    tables = query_api.query(query)

    values = []

    for table in tables:
        for record in table.records:
            values.append(record["_value"])

    print("VALUES:", values)

    
    return values