def calculate_health(sensor_data):

    score = 100

    moisture = sensor_data.get("moisture", 0)
    ph = sensor_data.get("ph", 7)
    ec = sensor_data.get("ec", 0)

    nitrogen = sensor_data.get("nitrogen", 0)
    phosphorus = sensor_data.get("phosphorus", 0)
    potassium = sensor_data.get("potassium", 0)

    # Moisture
    if moisture < 30:
        score -= 15

    # pH
    if ph < 6 or ph > 8:
        score -= 15

    # EC
    if ec > 1200:
        score -= 15

    # Nitrogen
    if nitrogen < 30:
        score -= 10

    # Phosphorus
    if phosphorus < 30:
        score -= 10

    # Potassium
    if potassium < 80:
        score -= 10

    return max(score, 0)