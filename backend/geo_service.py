import os
import json
import time
import urllib.request
import urllib.parse
import hashlib
from datetime import datetime, timezone
from population_service import PopulationService
from typing import List, Dict, Any

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
            with urllib.request.urlopen(req, timeout=30) as response:
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

    def get_empty_land(self, lat: float, lon: float, radius: int = 1000) -> Dict[str, Any]:
        """
        Fetch potentially empty / available land parcels near the given coordinates.
        Queries OSM for ways and relations tagged with landuse values that indicate
        undeveloped or lightly-developed land (vacant, brownfield, farmland, meadow,
        grass, greenfield) and returns them as a GeoJSON FeatureCollection with
        Polygon geometry so the map can render them as filled areas.
        """
        cache_key = f"empty_land_{lat}_{lon}_{radius}"
        cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
        cache_file = os.path.join(self.processed_dir, f"{cache_hash}_empty_land.json")

        if os.path.exists(cache_file):
            print(f"Loading empty land from cache: {cache_file}")
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        print(f"Fetching empty land from Overpass: lat={lat}, lon={lon}, radius={radius}")

        # Query for landuse polygons that indicate potentially available land.
        # 'out geom' gives us the full node list of each way/relation so we can
        # reconstruct polygon coordinates.
        query = f"""
        [out:json][timeout:30];
        (
          way["landuse"~"^(vacant|brownfield|farmland|meadow|grass|greenfield|landfill|quarry|allotments|orchard)$"](around:{radius},{lat},{lon});
          relation["landuse"~"^(vacant|brownfield|farmland|meadow|grass|greenfield|landfill|quarry|allotments|orchard)$"](around:{radius},{lat},{lon});
          way["leisure"~"^(park|garden|recreation_ground|nature_reserve)$"][!"name"](around:{radius},{lat},{lon});
        );
        out geom;
        """

        data = urllib.parse.urlencode({'data': query}).encode('utf-8')
        req = urllib.request.Request(
            self.overpass_url,
            data=data,
            headers={'User-Agent': 'GeoBusinessAI_App/1.0 (contact@geobusiness-ai.com)'}
        )

        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                raw_json = json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"Error fetching empty land from Overpass: {e}")
            raise

        features: List[Dict[str, Any]] = []

        LANDUSE_LABELS: Dict[str, str] = {
            'vacant':     'Vacant Land',
            'brownfield': 'Brownfield Site',
            'farmland':   'Farmland',
            'meadow':     'Meadow',
            'grass':      'Grassland',
            'greenfield': 'Greenfield Site',
            'landfill':   'Landfill',
            'quarry':     'Quarry',
            'allotments': 'Allotments',
            'orchard':    'Orchard',
            'park':       'Unnamed Park / Open Space',
            'garden':     'Garden / Open Space',
            'recreation_ground': 'Recreation Ground',
            'nature_reserve':    'Nature Reserve',
        }

        for element in raw_json.get('elements', []):
            tags  = element.get('tags', {})
            etype = element.get('type')

            landuse  = tags.get('landuse', '')
            leisure  = tags.get('leisure', '')
            land_key = landuse or leisure
            label    = LANDUSE_LABELS.get(land_key, land_key.replace('_', ' ').title())

            # --- Build polygon coordinates from way geometry ---
            if etype == 'way':
                geometry = element.get('geometry', [])
                if len(geometry) < 3:
                    continue
                coords = [[pt['lon'], pt['lat']] for pt in geometry]
                # Close the ring if not already closed
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                geojson_geom = {'type': 'Polygon', 'coordinates': [coords]}

            # --- For relations we use the bounding box as a rough polygon ---
            elif etype == 'relation':
                bounds = element.get('bounds')
                if not bounds:
                    continue
                minlat, minlon = bounds['minlat'], bounds['minlon']
                maxlat, maxlon = bounds['maxlat'], bounds['maxlon']
                coords = [
                    [minlon, minlat],
                    [maxlon, minlat],
                    [maxlon, maxlat],
                    [minlon, maxlat],
                    [minlon, minlat],
                ]
                geojson_geom = {'type': 'Polygon', 'coordinates': [coords]}
            else:
                continue

            # Estimate area in m² (rough, using mid-lat)
            ring = geojson_geom['coordinates'][0]
            lats = [p[1] for p in ring]
            lons = [p[0] for p in ring]
            lat_span = (max(lats) - min(lats)) * 111320
            lon_span = (max(lons) - min(lons)) * 111320 * abs(__import__('math').cos(__import__('math').radians(lat)))
            approx_area_m2 = lat_span * lon_span

            features.append({
                'type': 'Feature',
                'geometry': geojson_geom,
                'properties': {
                    'id':          f"{etype}/{element['id']}",
                    'name':        tags.get('name', label),
                    'landuse':     landuse,
                    'leisure':     leisure,
                    'land_type':   land_key,
                    'label':       label,
                    'approx_area_m2': round(approx_area_m2),
                    'tags':        tags,
                }
            })

        result = {
            'type': 'FeatureCollection',
            'metadata': {
                'center_lat':    lat,
                'center_lon':    lon,
                'radius_meters': radius,
                'total_parcels': len(features),
                'source':        'OpenStreetMap via Overpass API',
            },
            'features': features
        }

        # Cache the result
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)

        return result
