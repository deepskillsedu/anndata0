from app.farm_model import FARM
from app.influx_service import get_moisture_history
from app.trend_engine import calculate_trend
from app.history_engine import calculate_history_stats
from app.farm_config import FARM_CONFIG
from app.data_quality import get_data_quality


def build_twin(
    sensor_data,
    health_score,
    alerts,
    recommendations
):

    moisture_history = get_moisture_history()

    history_stats = calculate_history_stats(
    moisture_history
)
    

    data_quality = get_data_quality(
    history_stats["samples"]
)
    moisture_trend = calculate_trend(
        moisture_history
    )


    return {


        "twin": {
        "version": "1.0",
        "status": "ACTIVE"
            },

        "system": {
        "backend": "RUNNING",
        "mqtt": "CONNECTED",
        "influxdb": "CONNECTED"
            },

        "data_quality": {
        "samples": history_stats["samples"],
        "status": data_quality
            },

        "config": FARM_CONFIG,

        "farm_name": FARM["farm_name"],
        "field": FARM["field"],

        "zones": FARM["zones"],

        "health_score": health_score,

        "crop": {
            "name": "Tomato",
            "growth_stage": "Vegetative"
        },

        "sensors": {
            **sensor_data,

            "history": history_stats,

            "trends": {
            "moisture": moisture_trend
            }
        },

        "irrigation": {
            "status": "OFF"
        },

        "alerts": alerts,

        "recommendations": recommendations
    }