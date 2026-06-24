# from app.mongodb_service import actual_sensor_history


# def get_actual_history(limit=100):

#     cursor = (
#         actual_sensor_history
#         .find({}, {"_id": 0})
#         .sort("timestamp", -1)
#         .limit(limit)
#     )

#     return list(cursor)




from app.mongodb_service import actual_sensor_history, raw_sensor_history


def get_actual_history(thing_id, limit=100):

    cursor = (
        actual_sensor_history
        .find({"thingId": thing_id}, {"_id": 0})
        .sort("timestamp", -1)
        .limit(limit)
    )

    return list(cursor)



def get_raw_sensor_history(device_thing_id, limit=100):
    """
    Read-side counterpart to save_raw_sensor_history — the exact, untouched
    readings reported by one physical device thing (e.g. "smartfarm:s01"),
    with no farm-mapping filtering or simulation substitution applied.
    """

    cursor = (
        raw_sensor_history
        .find({"thingId": device_thing_id}, {"_id": 0})
        .sort("timestamp", -1)
        .limit(limit)
    )

    return list(cursor)