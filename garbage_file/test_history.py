from app.history_service import save_sensor_history

save_sensor_history({
    "moisture": 22.5,
    "temperature": 27.2,
    "ph": 6.8
})

print("saved")