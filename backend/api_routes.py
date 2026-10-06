import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, field_validator

import os
import joblib
import pandas as pd
import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from feature_engineer import SpatialFeatureEngineer
from explainability import explain_land_to_business, explain_business_to_land
from generate_dataset import generate_grid

# Configure logging before loading optional models so failures are reported safely.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load the pretrained budget model globally
BUDGET_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models', 'budget_model.pkl')
budget_model = None
try:
    budget_model = joblib.load(BUDGET_MODEL_PATH)
except Exception as e:
    logger.warning(f"Could not load budget_model.pkl: {e}")

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


class LandPriceResponse(BaseModel):
    price_per_cent: float
    currency: str = "INR"
    formatted_price: str
    confidence_low: Optional[float] = None
    confidence_high: Optional[float] = None
    source: str
    observed_at: Optional[str] = None
    sample_count: int = 0
    data_quality: str
    land_type: Optional[str] = None
    provenance_url: Optional[str] = None

# --- HELPER FUNCTIONS ---

def _get_input_features(lat, lon, radius, competitor_category='restaurant'):
    try:
        fv = engineer.generate_features(lat, lon, radius=radius, competitor_category=competitor_category)
    except Exception as e:
        logger.warning(f"Error fetching spatial features ({e}), using default baseline estimates.")
        fv = {
            'population_metrics': {'population': 4500, 'population_density': 1500, 'residential_density': 0.5},
            'spatial_metrics': {'road_density_km_per_sqkm': 6.0, 'distance_to_major_road_meters': 180},
            'amenity_counts': {'school_count': 1, 'college_count': 1, 'hospital_count': 1, 'bus_stop_count': 2}
        }
        
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


def _estimate_budget(df_input):
    """Estimate price per cent from the same spatial snapshot as a location."""
    pop_density = float(df_input.iloc[0]['population_density'])
    road_dist = float(df_input.iloc[0]['distance_to_major_road'])
    schools = float(df_input.iloc[0]['school_count'])
    hospitals = float(df_input.iloc[0]['hospital_count'])

    if budget_model is not None:
        features = pd.DataFrame({
            'population_density': [pop_density],
            'distance_to_major_road': [road_dist],
            'school_count': [schools],
            'hospital_count': [hospitals]
        })
        estimated_price = budget_model.predict(features)[0]
        source = 'Pretrained Model'
    else:
        density_factor = pop_density * 150
        road_factor = 200000 if 0 <= road_dist < 100 else (100000 if 0 <= road_dist < 500 else 0)
        estimated_price = 500000 + density_factor + road_factor
        source = 'Fallback'

    price_per_cent = max(100000, round(float(estimated_price), -3))
    return {
        'price_per_cent_inr': price_per_cent,
        'formatted_price': f'₹{price_per_cent:,.0f} per cent',
        'factors': {
            'source': source,
            'population_density': f'{pop_density:.1f}',
            'distance_to_road': f'{road_dist:.1f}m',
            'school_count': int(schools),
            'hospital_count': int(hospitals)
        }
    }

# --- LAND PRICE ADAPTERS ---

def _distance_meters(lat1, lon1, lat2, lon2):
    radius = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _normalized_price(price, source, quality, land_type=None, sample_count=0, observed_at=None, confidence=None, provenance_url=None):
    price = max(100000, round(float(price), -3))
    spread = confidence if confidence is not None else price * (0.15 if quality == 'medium' else 0.25)
    return {
        'price_per_cent': price,
        'currency': 'INR',
        'formatted_price': f'₹{price:,.0f} per cent',
        'confidence_low': max(0, round(price - spread, -3)),
        'confidence_high': round(price + spread, -3),
        'source': source,
        'observed_at': observed_at,
        'sample_count': sample_count,
        'data_quality': quality,
        'land_type': land_type,
        'provenance_url': provenance_url,
    }


def _price_from_provider(lat, lon, radius, land_type=None):
    provider_url = os.getenv('LAND_PRICE_PROVIDER_URL')
    if not provider_url:
        return None
    query = urllib.parse.urlencode({'lat': lat, 'lon': lon, 'radius': radius, 'land_type': land_type or ''})
    request = urllib.request.Request(f'{provider_url}?{query}', headers={'Accept': 'application/json', 'User-Agent': 'GeoBusinessAI/1.0'})
    with urllib.request.urlopen(request, timeout=8) as response:
        payload = json.loads(response.read().decode('utf-8'))
    price = payload.get('price_per_cent', payload.get('price'))
    if price is None:
        raise ValueError('Configured land-price provider did not return price_per_cent')
    spread = None
    if payload.get('confidence_low') is not None and payload.get('confidence_high') is not None:
        spread = (float(payload['confidence_high']) - float(payload['confidence_low'])) / 2
    return _normalized_price(price, payload.get('source', 'configured_provider'), payload.get('data_quality', 'medium'), payload.get('land_type', land_type), int(payload.get('sample_count', 0)), payload.get('observed_at'), spread, payload.get('provenance_url', provider_url))


def _price_from_csv(lat, lon, radius, land_type=None):
    csv_path = os.getenv('LAND_PRICE_DATA_PATH')
    if not csv_path or not os.path.exists(csv_path):
        return None
    data = pd.read_csv(csv_path)
    required = {'lat', 'lon', 'price_per_cent'}
    if not required.issubset(data.columns):
        raise ValueError(f'LAND_PRICE_DATA_PATH must contain {sorted(required)}')
    matches = []
    for row in data.to_dict('records'):
        if land_type and row.get('land_type') and str(row['land_type']).lower() != land_type.lower():
            continue
        distance = _distance_meters(lat, lon, float(row['lat']), float(row['lon']))
        if distance <= radius:
            matches.append(float(row['price_per_cent']))
    if not matches:
        return None
    median_price = float(pd.Series(matches).median())
    spread = max(median_price * 0.1, (max(matches) - min(matches)) / 2) if len(matches) > 1 else None
    return _normalized_price(median_price, 'local_transaction_csv', 'high' if len(matches) >= 5 else 'medium', land_type, len(matches), datetime.now(timezone.utc).date().isoformat(), spread, f'file://{csv_path}')


def _get_land_price(lat, lon, radius, land_type=None):
    """Provider -> local transaction CSV -> clearly labelled prototype fallback."""
    for adapter in (_price_from_provider, _price_from_csv):
        try:
            result = adapter(lat, lon, radius, land_type)
            if result:
                return result
        except Exception as error:
            logger.warning('Land-price adapter %s unavailable: %s', adapter.__name__, error)
    df_input, _ = _get_input_features(lat, lon, radius)
    fallback = _estimate_budget(df_input)
    price = fallback['price_per_cent_inr']
    return _normalized_price(price, 'prototype_budget_model', 'synthetic_fallback', land_type, 0, None, price * 0.25)


# --- ENDPOINTS ---

@router.get("/api/business-types")
def get_business_types():
    """Returns available business categories."""
    logger.info("Fetching business types")
    return {
        # These values map directly to categories collected from OpenStreetMap.
        "business_types": ["pharmacy", "grocery", "cafe", "restaurant", "bank", "clinic"]
    }

@router.get("/api/empty-land")
def get_empty_land(lat: float, lon: float, radius: int = 1000):
    """
    Returns a GeoJSON FeatureCollection of empty / available land parcels
    (vacant, brownfield, farmland, meadow, grass, greenfield, etc.)
    within the given radius around (lat, lon).

    Each feature has Polygon geometry and properties including:
      - name, land_type, label, approx_area_m2
    """
    logger.info(f"Fetching empty land for lat={lat}, lon={lon}, radius={radius}")
    try:
        result = engineer.geo_service.get_empty_land(lat, lon, radius)
        return result
    except Exception as e:
        logger.warning(f"Empty land fetch error ({e}), returning empty FeatureCollection.")
        return {"type": "FeatureCollection", "features": []}

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


@router.get("/api/land-price", response_model=LandPriceResponse)
def get_land_price(lat: float, lon: float, radius: int = 1000, land_type: Optional[str] = None):
    """Return normalized land-price data from a configured provider or local fallback."""
    if radius < 50 or radius > 10000:
        raise HTTPException(status_code=422, detail="radius must be between 50 and 10000 metres")
    try:
        return _get_land_price(lat, lon, radius, land_type)
    except Exception as e:
        logger.error(f"Land-price endpoint error: {e}")
        raise HTTPException(status_code=502, detail="Land-price provider unavailable")


@router.get("/api/estimate-budget")
def estimate_budget(lat: float, lon: float, radius: int = 500):
    """Estimate land price per cent for a specific clicked map location."""
    logger.info(f"Estimating budget for clicked land at {lat}, {lon}")
    try:
        df_input, _ = _get_input_features(lat, lon, radius)
        return _estimate_budget(df_input)
    except Exception as e:
        logger.error(f"Budget estimate error: {e}")
        raise HTTPException(status_code=500, detail="Failed to estimate land budget")

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
        
        budget_estimate = _estimate_budget(df_input)

        # Optionally save to DB here asynchronously (skipping hard failure if DB is offline)
        
        return {
            "lat": request.lat,
            "lon": request.lon,
            "radius": request.radius,
            "recommendations": results,
            "budget_estimate": budget_estimate
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
        
        import concurrent.futures

        def process_point(pt):
            lat, lon = pt
            df_input, fv = _get_input_features(lat, lon, 500, request.business_type)
            explanation = explain_business_to_land(df_input)
            
            return {
                "lat": lat,
                "lon": lon,
                "score": explanation["predicted_demand_score"],
                "model_score": explanation["predicted_demand_score"],
                "explanation": explanation,
                "budget_estimate": _estimate_budget(df_input),
                "details": {
                    "population": float(df_input.iloc[0]['population']),
                    "competitors": int(fv.get('amenity_counts', {}).get(request.business_type + '_count', 0)),
                    "schools": int(df_input.iloc[0]['school_count']),
                    "colleges": int(df_input.iloc[0]['college_count']),
                    "hospitals": int(df_input.iloc[0]['hospital_count']),
                    "bus_stops": int(df_input.iloc[0]['bus_stop_count']),
                    "road_density": float(df_input.iloc[0]['road_density']),
                    "distance_to_major_road": float(df_input.iloc[0]['distance_to_major_road'])
                }
            }
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            future_to_pt = {executor.submit(process_point, pt): pt for pt in points}
            for future in concurrent.futures.as_completed(future_to_pt):
                try:
                    candidates.append(future.result())
                except Exception as inner_e:
                    pt = future_to_pt[future]
                    logger.warning(f"Failed to process grid point {pt[0]},{pt[1]}: {inner_e}")
                
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
