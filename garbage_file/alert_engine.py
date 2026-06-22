def generate_alerts(sensor_data):

    alerts = []

    moisture = sensor_data.get("moisture")
    ph = sensor_data.get("ph")
    ec = sensor_data.get("ec")

    if moisture is not None and moisture < 30:
        alerts.append("Low Moisture")

    if ph is not None and ph < 6:
        alerts.append("Soil Too Acidic")

    if ph is not None and ph > 8:
        alerts.append("Soil Too Alkaline")

    if ec is not None and ec > 1200:
        alerts.append("High Soil Salinity")

    return alerts