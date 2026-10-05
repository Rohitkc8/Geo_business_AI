import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, field_validator

from feature_engineer import SpatialFeatureEngineer
from explainability import explain_land_to_business, explain_business_to_land
from generate_dataset import generate_grid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
engineer = SpatialFeatureEngineer()

# --- PYDANTIC MODELS ---

class AnalyzeLocationRequest(BaseModel):
    lat: float = Field(..., description="Latitude of the location")
    lon: float = Field(..., description="Longitude of the location")
    radius: int = Field(500, ge=50, le=5000, description="Analysis radius in meters")

class FindBestLocationsRequest(BaseModel):
    business_type: str = Field(..., description="Target business category (e.g., pharmacy, restaurant)")
    start_lat: float = Field(..., description="Starting latitude for search grid")
    start_lon: float = Field(..., description="Starting longitude for search grid")
    steps: int = Field(2, ge=1, le=10, description="Grid steps (e.g., 2 means 2x2 grid = 4 points)")
    step_size: float = Field(0.01, gt=0, le=0.05, description="Degree size between grid points")

    @field_validator('business_type')
    @classmethod
    def business_type_must_not_be_blank(cls, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise ValueError('business_type cannot be empty')
        return value

class LocationDetailsRequest(BaseModel):
    lat: float
    lon: float
    radius: int = 500

# --- HELPER FUNCTIONS ---

def _get_input_features(lat, lon, radius, competitor_category='restaurant'):
    try:
        fv = engineer.generate_features(lat, lon, radius=radius, competitor_category=competitor_category)
    except Exception as e:
        logger.error(f"Error fetching spatial features: {e}")
        raise HTTPException(status_code=502, detail="Error communicating with geographic services")
        
    pop_metrics = fv.get('population_metrics', {})
    spatial = fv.get('spatial_metrics', {})
    counts = fv.get('amenity_counts', {})
    
    input_data = {
        'population': pop_metrics.get('population') or 0,
        'population_density': pop_metrics.get('population_density') or 0,
        'residential_density': pop_metrics.get('residential_density') or 0,
        'road_density': spatial.get('road_density_km_per_sqkm') or 0,
        'distance_to_major_road': spatial.get('distance_to_major_road_meters') or 0,
        'school_count': counts.get('school_count') or 0,
        'college_count': counts.get('college_count') or 0,
        'hospital_count': counts.get('hospital_count') or 0,
        'bus_stop_count': counts.get('bus_stop_count') or 0
    }
    import pandas as pd
    return pd.DataFrame([input_data]), fv

# --- ENDPOINTS ---

@router.get("/api/business-types")
def get_business_types():
    """Returns available business categories."""
    logger.info("Fetching business types")
    return {
        # These values map directly to categories collected from OpenStreetMap.
        "business_types": ["pharmacy", "grocery", "cafe", "restaurant", "bank", "clinic"]
    }

@router.get("/api/location-details")
def get_location_details(lat: float, lon: float, radius: int = 500):
    """Returns basic geographic and demographic details for a location."""
    logger.info(f"Fetching location details for {lat}, {lon}")
    try:
        fv = engineer.generate_features(lat, lon, radius=radius)
        return fv
    except Exception as e:
        logger.error(f"Location details error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch location details")

@router.get("/api/map-data")
def get_map_data(lat: float, lon: float, radius: int = 500):
    """Returns raw GeoJSON features for map rendering."""
    logger.info(f"Fetching map data for {lat}, {lon}")
    try:
        raw_geo = engineer.geo_service.get_features(lat, lon, radius)
        # GeoDataService uses compact application records; Leaflet's GeoJSON
        # layer needs explicit geometry and properties.
        features = []
        for item in raw_geo.get("features", []):
            item_lat, item_lon = item.get("latitude"), item.get("longitude")
            if item_lat is None or item_lon is None:
                continue
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [item_lon, item_lat]},
                "properties": {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "category": item.get("category"),
                    **item.get("tags", {})
                }
            })
        return {"type": "FeatureCollection", "features": features}
    except Exception as e:
        logger.error(f"Map data error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch map data")

@router.post("/api/analyze-location")
def analyze_location(request: AnalyzeLocationRequest):
    """
    LAND -> BUSINESS FLOW
    Analyzes a specific location and returns the predicted viability for various business types.
    """
    logger.info(f"Analyzing location: {request.lat}, {request.lon}")
    try:
        df_input, _ = _get_input_features(request.lat, request.lon, request.radius)
        results = explain_land_to_business(df_input)
        
        # Optionally save to DB here asynchronously (skipping hard failure if DB is offline)
        
        return {
            "lat": request.lat,
            "lon": request.lon,
            "radius": request.radius,
            "recommendations": results
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Analyze location error: {e}")
        raise HTTPException(status_code=500, detail="Model 1 inference failed")

@router.post("/api/find-best-locations")
def find_best_locations(request: FindBestLocationsRequest):
    """
    BUSINESS -> LAND FLOW
    Scans a geographic grid to find the optimal locations for a specific business type.
    """
    logger.info(f"Finding best locations for {request.business_type} near {request.start_lat}, {request.start_lon}")
    try:
        # Make the selected area the centre of the candidate grid.  The previous
        # implementation treated it as the south-west corner, which made results
        # appear outside the area the user searched for.
        offset = (request.steps - 1) / 2
        points = [
            (
                request.start_lat + (row - offset) * request.step_size,
                request.start_lon + (column - offset) * request.step_size,
            )
            for row in range(request.steps)
            for column in range(request.steps)
        ]
        candidates = []
        
        for lat, lon in points:
            try:
                df_input, fv = _get_input_features(lat, lon, 500, request.business_type)
                explanation = explain_business_to_land(df_input)
                
                candidates.append({
                    "lat": lat,
                    "lon": lon,
                    # This is the direct output of Model 2.  It is deliberately
                    # not normalised, bucketed, or otherwise manufactured here.
                    "score": explanation["predicted_demand_score"],
                    "model_score": explanation["predicted_demand_score"],
                    "explanation": explanation,
                    "details": {
                        # Convert pandas/NumPy scalar values into plain JSON
                        # numbers before FastAPI serialises the response.
                        "population": float(df_input.iloc[0]['population']),
                        "competitors": int(fv.get('amenity_counts', {}).get(request.business_type + '_count', 0)),
                        "schools": int(df_input.iloc[0]['school_count']),
                        "colleges": int(df_input.iloc[0]['college_count']),
                        "hospitals": int(df_input.iloc[0]['hospital_count']),
                        "bus_stops": int(df_input.iloc[0]['bus_stop_count']),
                        "road_density": float(df_input.iloc[0]['road_density']),
                        "distance_to_major_road": float(df_input.iloc[0]['distance_to_major_road'])
                    }
                })
            except Exception as inner_e:
                logger.warning(f"Failed to process grid point {lat},{lon}: {inner_e}")
                continue
                
        if not candidates:
            raise HTTPException(status_code=404, detail="Could not successfully evaluate any candidates in this grid.")
            
        # Rank from highest score to lowest
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "business_type": request.business_type,
            "model": "business_location_model (Model 2)",
            "cell_size_degrees": request.step_size,
            "candidates": candidates
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Find best locations error: {e}")
        raise HTTPException(status_code=500, detail="Model 2 inference failed")
