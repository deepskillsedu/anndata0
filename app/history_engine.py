def calculate_history_stats(values):

    if not values:
        return {
            "samples": 0,
            "min": None,
            "max": None,
            "avg": None
        }

    return {
        "samples": len(values),
        "min": min(values),
        "max": max(values),
        "avg": round(sum(values) / len(values), 2)
    }