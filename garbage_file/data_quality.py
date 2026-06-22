def get_data_quality(sample_count):

    if sample_count >= 100:
        return "GOOD"

    if sample_count >= 20:
        return "FAIR"

    return "POOR"