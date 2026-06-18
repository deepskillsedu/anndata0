# from datetime import datetime

# from app.mongodb_service import (
#     actual_sensor_history,
#     actual_override_history,
#     virtual_history
# )


# def save_actual_sensor_history(data):

#     document = {
#         "timestamp": datetime.utcnow(),
#         **data
#     }

#     actual_sensor_history.insert_one(document)


# def save_actual_override(
#     property_name,
#     before_state,
#     after_state
# ):

#     document = {
#         "timestamp": datetime.utcnow(),
#         "overrideProperty": property_name,
#         "before": before_state,
#         "after": after_state,
#         "source": "dashboard"
#     }

#     actual_override_history.insert_one(document)


# def save_virtual_change(
#     property_name,
#     before_state,
#     after_state
# ):

#     document = {
#         "timestamp": datetime.utcnow(),
#         "changedProperty": property_name,
#         "before": before_state,
#         "after": after_state,
#         "source": "dashboard"
#     }

#     virtual_history.insert_one(document)




from datetime import datetime

from app.mongodb_service import (
    actual_sensor_history,
    actual_override_history,
    virtual_history
)


def save_actual_sensor_history(data, thing_id="smartfarm:twin01"):

    document = {
        "timestamp": datetime.utcnow(),
        "thingId": thing_id,
        **data
    }

    actual_sensor_history.insert_one(document)


def save_actual_override(
    property_name,
    before_state,
    after_state,
    thing_id="smartfarm:twin01"
):

    document = {
        "timestamp": datetime.utcnow(),
        "thingId": thing_id,
        "overrideProperty": property_name,
        "before": before_state,
        "after": after_state,
        "source": "dashboard"
    }

    actual_override_history.insert_one(document)


def save_virtual_change(
    property_name,
    before_state,
    after_state,
    thing_id="smartfarm:twin01"
):

    document = {
        "timestamp": datetime.utcnow(),
        "thingId": thing_id,
        "changedProperty": property_name,
        "before": before_state,
        "after": after_state,
        "source": "dashboard"
    }

    virtual_history.insert_one(document)