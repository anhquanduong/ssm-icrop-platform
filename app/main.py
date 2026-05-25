from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import pandas as pd
from app.core.weather_api import fetch_openmeteo_weather

app = FastAPI(
    title="SSM-iCrop API Platform",
    description="High-performance backend services for the SSM-iCrop crop growth simulation platform.",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimulationRequest(BaseModel):
    latitude: float
    longitude: float
    start_date: str
    end_date: str
    crop_type: str
    soil_type: Optional[str] = "Clay-Loam"

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "SSM-iCrop Engine Gateway",
        "version": "1.0.0"
    }

@app.get("/api/weather")
def get_weather(lat: float, lon: float, start_date: str, end_date: str):
    """
    Fetch daily weather data from Open-Meteo API.
    """
    try:
        df = fetch_openmeteo_weather(lat, lon, start_date, end_date)
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/simulate")
def run_simulation(request: SimulationRequest):
    """
    Endpoint to trigger SSM-iCrop crop growth simulation.
    """
    try:
        # TODO: Integrate SSM-iCrop model engine calculation
        # This will load parameters from core/model_engine and weather data from weather_api
        return {
            "status": "success",
            "message": "Simulation executed successfully",
            "metadata": {
                "latitude": request.latitude,
                "longitude": request.longitude,
                "start_date": request.start_date,
                "end_date": request.end_date,
                "crop_type": request.crop_type
            },
            "results": {
                "LAI_max": 4.5,
                "biomass_yield_t_ha": 8.2,
                "grain_yield_t_ha": 6.8
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
