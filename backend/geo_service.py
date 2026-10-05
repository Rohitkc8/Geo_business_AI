import os
import json
import time
import urllib.request
import urllib.parse
import hashlib
from datetime import datetime, timezone
from population_service import PopulationService

# Ensure directories exist
RAW_DIR = os.path.join(os.path.dirname(__file__), 'data', 'raw')
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), 'data', 'processed')

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

class GeoDataService:
    def __init__(self, cache_dir_raw=RAW_DIR, cache_dir_processed=PROCESSED_DIR):
        self.raw_dir = cache_dir_raw
        self.processed_dir = cache_dir_processed
        self.overpass_url = "https://overpass-api.de/api/interpreter"
        self.population_service = PopulationService()

    def get_features(self, lat: float, lon: float, radius: int = 1000):
        """
        Fetch geographic features from Overpass API or cache.
        """
        # Create a unique query hash based on inputs
        query_key = f"{lat}_{lon}_{radius}"
        query_hash = hashlib.md5(query_key.encode('utf-8')).hexdigest()
        
        raw_file = os.path.join(self.raw_dir, f"{query_hash}.json")
        processed_file = os.path.join(self.processed_dir, f"{query_hash}.json")
        
        # Check cache
        if os.path.exists(processed_file):
            print(f"Loading from cache: {processed_file}")
            with open(processed_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        print(f"Fetching from Overpass API: lat={lat}, lon={lon}, radius={radius}")
        
        # Construct Overpass QL query
        # Fetching amenities, shops, offices, highway (roads/bus stops), etc.
        query = f"""
        [out:json][timeout:25];
        (
          node["amenity"~"restaurant|cafe|fast_food|pharmacy|bank|school|college|university|hospital|clinic|doctors"](around:{radius},{lat},{lon});
          way["amenity"~"restaurant|cafe|fast_food|pharmacy|bank|school|college|university|hospital|clinic|doctors"](around:{radius},{lat},{lon});
          
          node["shop"](around:{radius},{lat},{lon});
          way["shop"](around:{radius},{lat},{lon});
          
          node["office"](around:{radius},{lat},{lon});
          way["office"](around:{radius},{lat},{lon});
          
          node["highway"~"bus_stop|platform"](around:{radius},{lat},{lon});
          way["highway"](around:{radius},{lat},{lon});
        );
        out center;
        """
        
        data = urllib.parse.urlencode({'data': query}).encode('utf-8')
        req = urllib.request.Request(
            self.overpass_url, 
            data=data,
            headers={'User-Agent': 'GeoBusinessAI_App/1.0 (contact@geobusiness-ai.com)'}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                raw_data = response.read().decode('utf-8')
                raw_json = json.loads(raw_data)
                
                # Save raw response
                with open(raw_file, 'w', encoding='utf-8') as f:
                    json.dump(raw_json, f, indent=2)
                
                # Process the data
                processed_json = self._process_data(raw_json, lat, lon, radius, query_hash)
                
                # Save processed data
                with open(processed_file, 'w', encoding='utf-8') as f:
                    json.dump(processed_json, f, indent=2)
                
                return processed_json
                
        except Exception as e:
            print(f"Error fetching from Overpass: {e}")
            raise

    def _process_data(self, raw_json, lat, lon, radius, query_hash):
        features = []
        for element in raw_json.get('elements', []):
            tags = element.get('tags', {})
            
            # Determine coordinates (ways use 'center', nodes use 'lat'/'lon')
            item_lat = element.get('lat') or (element.get('center', {}).get('lat'))
            item_lon = element.get('lon') or (element.get('center', {}).get('lon'))
            
            if item_lat is None or item_lon is None:
                continue

            # Categorize the feature
            category = self._categorize_feature(tags)
            
            features.append({
                'id': f"{element['type']}/{element['id']}",
                'name': tags.get('name', 'Unnamed Feature'),
                'category': category,
                'latitude': item_lat,
                'longitude': item_lon,
                'tags': tags
            })

        # Fetch population data for the same radius
        population_data = self.population_service.get_population_for_radius(lat, lon, radius)

        # Add Metadata
        result = {
            'metadata': {
                'source': 'OpenStreetMap via Overpass API',
                'query_params': {
                    'center_latitude': lat,
                    'center_longitude': lon,
                    'radius_meters': radius
                },
                'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                'query_hash': query_hash,
                'license': 'Data © OpenStreetMap contributors, ODbL 1.0. http://osm.org/copyright',
                'disclaimer': 'Do not assume absence from OSM means actual absence in reality. No missing features have been fabricated.'
            },
            'summary': {
                'total_features': len(features)
            },
            'population_metrics': population_data,
            'features': features
        }
        
        return result

    def _categorize_feature(self, tags):
        if 'amenity' in tags:
            amenity = tags['amenity']
            if amenity in ['restaurant', 'cafe', 'fast_food']:
                return 'restaurant'
            elif amenity == 'pharmacy':
                return 'pharmacy'
            elif amenity == 'bank':
                return 'bank'
            elif amenity in ['school', 'college', 'university']:
                return 'education'
            elif amenity in ['hospital', 'clinic', 'doctors']:
                return 'healthcare'
        
        if 'shop' in tags:
            shop = tags['shop']
            if shop in ['supermarket', 'convenience', 'grocery']:
                return 'grocery_store'
            return f"shop_{shop}"
            
        if 'office' in tags:
            return 'office'
            
        if 'highway' in tags:
            highway = tags['highway']
            if highway in ['bus_stop', 'platform']:
                return 'bus_stop'
            return 'road'
            
        return 'other'
