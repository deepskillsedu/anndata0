# import time

# from app.ditto_reader import get_actual
# from app.history_service import save_actual_sensor_history


# def start_history_logger():

#     while True:

#         try:

#             actual = get_actual()

#             save_actual_sensor_history(actual)

#             print("history saved")

#         except Exception as e:

#             print("history logger error:", e)

#         time.sleep(30)



import time

from app.ditto_reader import get_actual
from app.farm_registry import list_farm_thing_ids
from app.history_service import save_actual_sensor_history


def start_history_logger():

    while True:

        try:
            thing_ids = list_farm_thing_ids()
        except Exception as e:
            print("could not list farms:", e)
            thing_ids = []

        for thing_id in thing_ids:

            try:
                actual = get_actual(thing_id)
                save_actual_sensor_history(actual, thing_id=thing_id)
                print(f"history saved: {thing_id}")

            except Exception as e:
                print(f"history logger error ({thing_id}):", e)

        time.sleep(30)