import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import pandas as pd

from feature_engineer import SpatialFeatureEngineer
from explainability import explain_land_to_business, explain_business_to_land

router = APIRouter()
engineer = SpatialFeatureEngineer()

class LandRequest(BaseModel):
    lat: float
    lon: float
    radius: int = 500

class BusinessRequest(BaseModel):
    lat: float
    lon: float
    business_type: str
    radius: int = 500

def _get_input_features(lat, lon, radius, competitor_category='restaurant'):
    fv = engineer.generate_features(lat, lon, radius=radius, competitor_category=competitor_category)
    pop_metrics = fv['population_metrics']
    spatial = fv['spatial_metrics']
    counts = fv['amenity_counts']
    
    input_data = {
        'population': pop_metrics['population'] if pop_metrics['population'] is not None else 0,
        'population_density': pop_metrics['population_density'] if pop_metrics['population_density'] is not None else 0,
        'residential_density': pop_metrics['residential_density'] if pop_metrics['residential_density'] is not None else 0,
        'road_density': spatial['road_density_km_per_sqkm'],
        'distance_to_major_road': spatial['distance_to_major_road_meters'],
        'school_count': counts['school_count'],
        'college_count': counts['college_count'],
        'hospital_count': counts['hospital_count'],
        'bus_stop_count': counts['bus_stop_count']
    }
    return pd.DataFrame([input_data])

@router.post("/api/predict/land_to_business")
def predict_land_to_business(request: LandRequest):
    try:
        # Build features DataFrame
        df_input = _get_input_features(request.lat, request.lon, request.radius)
        
        # Get explanations
        results = explain_land_to_business(df_input)
        return {"predictions": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/predict/business_to_land")
def predict_business_to_land(request: BusinessRequest):
    try:
        df_input = _get_input_features(request.lat, request.lon, request.radius, request.business_type)
        
        result = explain_business_to_land(df_input)
        return {
            "business_type": request.business_type,
            "lat": request.lat,
            "lon": request.lon,
            "explanation": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
