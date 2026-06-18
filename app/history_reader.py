# from app.mongodb_service import actual_sensor_history


# def get_actual_history(limit=100):

#     cursor = (
#         actual_sensor_history
#         .find({}, {"_id": 0})
#         .sort("timestamp", -1)
#         .limit(limit)
#     )

#     return list(cursor)





from app.mongodb_service import actual_sensor_history


def get_actual_history(thing_id="smartfarm:twin01", limit=100):

    cursor = (
        actual_sensor_history
        .find({"thingId": thing_id}, {"_id": 0})
        .sort("timestamp", -1)
        .limit(limit)
    )

    return list(cursor)
