from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")   # real connection string here
db = client["smart_farm"]                              #  real db name here

actual_sensor_history = db["actual_sensor_history"]
actual_override_history = db["actual_override_history"]
virtual_sensor_history = db["virtual_sensor_history"]
raw_sensor_history = db["raw_sensor_history"]

farm_images = db["farm_images"] # to store images for farms
farm_image_history = db["farm_image_history"] 