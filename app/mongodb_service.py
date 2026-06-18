from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")

db = client["smart_farm"]

actual_sensor_history = db["actual_sensor_history"]
actual_override_history = db["actual_override_history"]
virtual_history = db["virtual_history"]