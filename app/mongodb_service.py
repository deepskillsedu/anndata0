from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")

db = client["smart_farm"]

actual_sensor_history = db["actual_sensor_history"]
actual_override_history = db["actual_override_history"]
virtual_history = db["virtual_history"]

# Periodic full-feature snapshots of each farm's virtual properties —
# the direct counterpart to actual_sensor_history. virtual_history
# (above) holds discrete before/after EDIT events from save_virtual_change();
# this collection holds whole-feature SNAPSHOTS on a timer, exactly like
# actual_sensor_history does for the actual feature. Kept separate so a
# later query never has to guess whether a document is an edit-diff or
# a full snapshot.
virtual_sensor_history = db["virtual_sensor_history"]