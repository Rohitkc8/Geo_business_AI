from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import urllib.request
import urllib.parse
import json

app = FastAPI(title="GeoBusiness AI API")

# Setup CORS to allow React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GeocodeRequest(BaseModel):
    query: str

class GeocodeResponse(BaseModel):
    latitude: float
    longitude: float
    display_name: str

# Simple in-memory cache for geocoding
geocode_cache = {}

@app.get("/")
def health_check():
    return {
        "status": "ok",
        "project": "GeoBusiness AI"
    }

import ssl

@app.post("/api/geocode", response_model=GeocodeResponse)
def geocode(request: GeocodeRequest):
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    query_key = query.lower()
    # Check cache
    if query_key in geocode_cache:
        return geocode_cache[query_key]

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    candidates = [query]
    if "," not in query:
        candidates.extend([f"{query}, Tamil Nadu, India", f"{query}, India"])

    # 1. Try Photon API first (fast, resilient, handles partial & fuzzy names)
    for q_try in candidates:
        try:
            url = f"https://photon.komoot.io/api/?q={urllib.parse.quote(q_try)}&limit=1"
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'GeoBusinessAI_App/1.0 (contact@geobusiness-ai.com)'}
            )
            with urllib.request.urlopen(req, timeout=3, context=ctx) as response:
                data = json.loads(response.read().decode())
                features = data.get("features", [])
                if features and len(features) > 0:
                    feat = features[0]
                    coords = feat.get("geometry", {}).get("coordinates", [])
                    props = feat.get("properties", {})
                    if len(coords) >= 2:
                        name_parts = [props.get("name"), props.get("district"), props.get("city"), props.get("state"), props.get("country")]
                        display_name = ", ".join([p for p in name_parts if p]) or q_try
                        response_data = GeocodeResponse(
                            latitude=float(coords[1]),
                            longitude=float(coords[0]),
                            display_name=display_name
                        )
                        geocode_cache[query_key] = response_data
                        return response_data
        except Exception:
            pass

    # 2. Fallback to OpenStreetMap Nominatim
    for q_try in candidates:
        try:
            url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(q_try)}&format=json&limit=1"
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'GeoBusinessAI_App/1.0 (contact@geobusiness-ai.com)'}
            )
            with urllib.request.urlopen(req, timeout=5, context=ctx) as response:
                data = json.loads(response.read().decode())
                if data and len(data) > 0:
                    result = data[0]
                    response_data = GeocodeResponse(
                        latitude=float(result["lat"]),
                        longitude=float(result["lon"]),
                        display_name=result.get("display_name", q_try)
                    )
                    geocode_cache[query_key] = response_data
                    return response_data
        except Exception:
            pass

    raise HTTPException(status_code=404, detail=f"Could not locate '{query}'. Try including a city or state name (e.g. '{query}, Salem').")

# Include ML Predict Routers
from api_routes import router as ml_router
app.include_router(ml_router)

