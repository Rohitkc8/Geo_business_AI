import urllib.request
import urllib.parse
import json
import math
import hashlib
import os

CACHE_DIR = os.path.join(os.path.dirname(__file__), 'data', 'population_cache')
os.makedirs(CACHE_DIR, exist_ok=True)

class PopulationService:
    def __init__(self, cache_dir=CACHE_DIR):
        self.cache_dir = cache_dir
        self.base_url = "https://api.worldpop.org/v1/services/stats"
        self.year = "2020" # WorldPop reliable static dataset year

    def get_population_for_radius(self, lat: float, lon: float, radius_meters: int):
        # Calculate a bounding box polygon for the radius
        # 1 degree of latitude is ~111,111 meters
        lat_offset = radius_meters / 111111.0
        lon_offset = radius_meters / (111111.0 * math.cos(math.radians(lat)))
        
        min_lat = lat - lat_offset
        max_lat = lat + lat_offset
        min_lon = lon - lon_offset
        max_lon = lon + lon_offset

        # GeoJSON Polygon requires closing the loop
        polygon_coords = [
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat],
            [min_lon, min_lat]
        ]
        
        area_sq_km = (radius_meters * 2 / 1000.0) ** 2 # approximate bounding box area
        
        return self._fetch_population(polygon_coords, area_sq_km)

    def _fetch_population(self, polygon_coords, area_sq_km):
        query_key = json.dumps(polygon_coords)
        query_hash = hashlib.md5(query_key.encode('utf-8')).hexdigest()
        cache_file = os.path.join(self.cache_dir, f"{query_hash}.json")
        
        if os.path.exists(cache_file):
            print(f"Loading population from cache: {cache_file}")
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        print(f"Fetching population data from WorldPop...")
        geojson = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [polygon_coords]
                }
            }]
        }

        params = {
            "dataset": "wpgppop",
            "year": self.year,
            "runasync": "false",
            "geojson": json.dumps(geojson)
        }
        
        url = self.base_url + "?" + urllib.parse.urlencode(params)
        
        result = {
            "population": None,
            "population_density": None,
            "households": None,
            "data_source": "WorldPop API",
            "data_year": int(self.year),
            "is_historical_estimate": True,
            "coverage_status": "limited",
            "area_sq_km": round(area_sq_km, 2)
        }
        
        try:
            req = urllib.request.Request(url)
            res = urllib.request.urlopen(req, timeout=30)
            data = json.loads(res.read().decode())
            
            if data.get('error') is False and 'data' in data:
                total_pop = data['data'].get('total_population')
                
                if total_pop is not None and total_pop > 0:
                    total_pop = int(total_pop)
                    result['population'] = total_pop
                    result['population_density'] = round(total_pop / area_sq_km, 2)
                    result['coverage_status'] = "good"
                else:
                    # No data found in this grid or 0 population
                    result['coverage_status'] = "limited"
            
        except Exception as e:
            print(f"Error fetching population data: {e}")
            result['coverage_status'] = "error"
            
        # Cache the result to avoid spamming the API
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
            
        return result
