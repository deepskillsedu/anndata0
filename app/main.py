from fastapi import FastAPI
from app.influx_service import get_latest_data
from app.alert_engine import generate_alerts
from app.health_engine import calculate_health
from app.recommendation_engine import generate_recommendations
from app.farm_model import FARM
from app.twin_builder import build_twin
from app.influx_service import get_moisture_history
from fastapi import Request
from fastapi.templating import Jinja2Templates
from app.ditto_service import update_ditto

app = FastAPI(
    title="Smart Farm Digital Twin",
    version="1.0.0"
)

templates = Jinja2Templates(
    directory="templates"
)


@app.get("/")
def root():
    return {
        "project": "Smart Farm Digital Twin",
        "status": "running"
    }


@app.get("/health")
def health():
    return {
        "backend": "healthy"
    }


@app.get("/farm/live")
def farm_live():
    return get_latest_data()


@app.get("/farm/twin")
def farm_twin():

    sensor_data = get_latest_data()

    alerts = generate_alerts(sensor_data)

    health_score = calculate_health(sensor_data)

    recommendations = generate_recommendations(sensor_data)

    return build_twin(
    sensor_data,
    health_score,
    alerts,
    recommendations
)

@app.get("/farm/history/moisture")
def moisture_history():

    return {
        "values": get_moisture_history()
    }

@app.get("/dashboard")
def dashboard(request: Request):

    sensor_data = get_latest_data()

    alerts = generate_alerts(sensor_data)

    health_score = calculate_health(sensor_data)

    recommendations = generate_recommendations(sensor_data)

    twin = build_twin(
        sensor_data,
        health_score,
        alerts,
        recommendations
    )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "twin": twin
        }
    )