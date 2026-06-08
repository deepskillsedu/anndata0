def calculate_trend(values):

    if len(values) < 2:
        return "UNKNOWN"

    first = values[0]
    last = values[-1]

    difference = last - first

    if difference > 0.5:
        return "RISING"

    elif difference < -0.5:
        return "FALLING"

    return "STABLE"