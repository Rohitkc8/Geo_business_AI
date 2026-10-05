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
    allow_origins=["*"], # For development, we allow all
    allow_credentials=True,
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

@app.post("/api/geocode", response_model=GeocodeResponse)
def geocode(request: GeocodeRequest):
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Check cache
    if query in geocode_cache:
        return geocode_cache[query]

    # Use Nominatim API
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=1"
    
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'GeoBusinessAI_App/1.0 (contact@geobusiness-ai.com)'}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if not data:
                raise HTTPException(status_code=404, detail="Location not found")
            
            result = data[0]
            lat = float(result["lat"])
            lon = float(result["lon"])
            display_name = result["display_name"]
            
            response_data = GeocodeResponse(
                latitude=lat,
                longitude=lon,
                display_name=display_name
            )
            
            # Save to cache
            geocode_cache[query] = response_data
            return response_data
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Failed to geocode location")

# Include ML Predict Routers
from api_routes import router as ml_router
app.include_router(ml_router)
