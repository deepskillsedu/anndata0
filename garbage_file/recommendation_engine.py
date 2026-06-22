def generate_recommendations(sensor_data):

    recommendations = []

    moisture = sensor_data.get("moisture", 0)
    ph = sensor_data.get("ph", 7)
    ec = sensor_data.get("ec", 0)

    nitrogen = sensor_data.get("nitrogen", 0)
    phosphorus = sensor_data.get("phosphorus", 0)
    potassium = sensor_data.get("potassium", 0)

    if moisture < 30:
        recommendations.append(
            "Increase irrigation frequency"
        )

    if ph < 6:
        recommendations.append(
            "Apply lime to raise soil pH"
        )

    if ph > 8:
        recommendations.append(
            "Use sulfur-based amendment"
        )

    if ec > 1200:
        recommendations.append(
            "Flush soil with clean water"
        )

    if nitrogen < 30:
        recommendations.append(
            "Apply nitrogen fertilizer"
        )

    if phosphorus < 30:
        recommendations.append(
            "Apply phosphorus fertilizer"
        )

    if potassium < 80:
        recommendations.append(
            "Apply potassium fertilizer"
        )

    # Add this block here
    if len(recommendations) == 0:
        recommendations.append(
            "Farm conditions are optimal"
        )

    return recommendations