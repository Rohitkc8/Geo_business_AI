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

import ssl

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter"
]

class GeoDataService:
    def __init__(self, cache_dir_raw=RAW_DIR, cache_dir_processed=PROCESSED_DIR):
        self.raw_dir = cache_dir_raw
        self.processed_dir = cache_dir_processed
        self.population_service = PopulationService()

    def _query_overpass(self, query: str, timeout: int = 25) -> Dict[str, Any]:
        """
        Execute an Overpass query against multiple mirror endpoints with fallback.
        """
        data = urllib.parse.urlencode({'data': query}).encode('utf-8')
        last_err = None
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        for endpoint in OVERPASS_SERVERS:
            try:
                req = urllib.request.Request(
                    endpoint,
                    data=data,
                    headers={'User-Agent': 'GeoBusinessAI_App/1.0 (contact@geobusiness-ai.com)'}
                )
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
                    raw_data = response.read().decode('utf-8')
                    return json.loads(raw_data)
            except Exception as e:
                last_err = e
                print(f"Overpass mirror {endpoint} failed ({e}), trying next mirror...")
                time.sleep(0.3)

        print(f"All Overpass mirrors failed: {last_err}. Returning empty response fallback.")
        return {"elements": []}

    def get_features(self, lat: float, lon: float, radius: int = 1000):
        """
        Fetch geographic features from Overpass API or cache.
        """
        # Create a unique query hash based on inputs (v3 to include hotels, barber shops, optimized roads)
        query_key = f"{lat}_{lon}_{radius}_v3"
        query_hash = hashlib.md5(query_key.encode('utf-8')).hexdigest()
        
        raw_file = os.path.join(self.raw_dir, f"{query_hash}.json")
        processed_file = os.path.join(self.processed_dir, f"{query_hash}.json")
        
        # Check cache
        if os.path.exists(processed_file):
            print(f"Loading from cache: {processed_file}")
            with open(processed_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        print(f"Fetching from Overpass API: lat={lat}, lon={lon}, radius={radius}")
        
        query = f"""
        [out:json][timeout:25];
        (
          node["amenity"~"restaurant|cafe|fast_food|pharmacy|bank|school|college|university|hospital|clinic|doctors|barber"](around:{radius},{lat},{lon});
          way["amenity"~"restaurant|cafe|fast_food|pharmacy|bank|school|college|university|hospital|clinic|doctors|barber"](around:{radius},{lat},{lon});
          relation["amenity"~"restaurant|cafe|fast_food|pharmacy|bank|school|college|university|hospital|clinic|doctors|barber"](around:{radius},{lat},{lon});
          
          node["tourism"~"hotel|motel|guest_house|hostel"](around:{radius},{lat},{lon});
          way["tourism"~"hotel|motel|guest_house|hostel"](around:{radius},{lat},{lon});
          relation["tourism"~"hotel|motel|guest_house|hostel"](around:{radius},{lat},{lon});
          
          node["shop"](around:{radius},{lat},{lon});
          way["shop"](around:{radius},{lat},{lon});
          relation["shop"](around:{radius},{lat},{lon});
          
          node["office"](around:{radius},{lat},{lon});
          way["office"](around:{radius},{lat},{lon});
          relation["office"](around:{radius},{lat},{lon});
          
          node["highway"~"bus_stop|platform"](around:{radius},{lat},{lon});
          way["highway"~"primary|secondary|tertiary|trunk|motorway|residential"](around:{radius},{lat},{lon});
          relation["highway"~"bus_stop|platform"](around:{radius},{lat},{lon});
        );
        out center;
        """
        
        raw_json = self._query_overpass(query, timeout=25)
        
        # Save raw response if non-empty
        if raw_json.get('elements'):
            with open(raw_file, 'w', encoding='utf-8') as f:
                json.dump(raw_json, f, indent=2)
        
        # Process the data
        processed_json = self._process_data(raw_json, lat, lon, radius, query_hash)
        
        # Save processed data
        if processed_json.get('features'):
            with open(processed_file, 'w', encoding='utf-8') as f:
                json.dump(processed_json, f, indent=2)
        
        return processed_json

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
        if tags.get('tourism') in ['hotel', 'motel', 'guest_house', 'hostel'] or tags.get('building') == 'hotel':
            return 'hotel'

        if (
            tags.get('shop') in ['hairdresser', 'barber', 'salon', 'beauty', 'hairdresser_barber']
            or tags.get('amenity') == 'barber'
            or tags.get('hairdresser') == 'barber'
        ):
            return 'barber'

        if 'amenity' in tags:
            amenity = tags['amenity']
            if amenity == 'cafe':
                return 'cafe'
            elif amenity in ['restaurant', 'fast_food']:
                return 'restaurant'
            elif amenity == 'pharmacy':
                return 'pharmacy'
            elif amenity == 'bank':
                return 'bank'
            elif amenity in ['college', 'university']:
                return 'college'
            elif amenity == 'school':
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

        Each feature's properties now also include a 'surroundings' sub-object
        with nearby amenity counts (schools, hospitals, restaurants, pharmacies,
        bus_stops, roads) fetched within 500 m of the parcel centroid.
        """
        import math

        cache_key = f"empty_land_v2_{lat}_{lon}_{radius}"
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

        raw_json = self._query_overpass(query, timeout=30)

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
            lon_span = (max(lons) - min(lons)) * 111320 * abs(math.cos(math.radians(lat)))
            approx_area_m2 = lat_span * lon_span

            # Centroid of the parcel (simple average of ring vertices)
            centroid_lat = sum(lats) / len(lats)
            centroid_lon = sum(lons) / len(lons)

            features.append({
                'type': 'Feature',
                'geometry': geojson_geom,
                'properties': {
                    'id':            f"{etype}/{element['id']}",
                    'name':          tags.get('name', label),
                    'landuse':       landuse,
                    'leisure':       leisure,
                    'land_type':     land_key,
                    'label':         label,
                    'approx_area_m2': round(approx_area_m2),
                    'centroid_lat':  round(centroid_lat, 6),
                    'centroid_lon':  round(centroid_lon, 6),
                    'tags':          tags,
                    # surroundings populated below
                    'surroundings':  {},
                }
            })

        # --- Enrich each parcel with surroundings (amenity counts within 500 m) ---
        # We issue ONE batch Overpass query containing union clauses for all centroids
        # to avoid N separate HTTP calls.
        SURROUND_RADIUS = 500
        if features:
            surround_query_parts = []
            for feat in features:
                clat = feat['properties']['centroid_lat']
                clon = feat['properties']['centroid_lon']
                surround_query_parts.append(
                    f'node["amenity"~"school|college|university|hospital|clinic|doctors|restaurant|cafe|fast_food|pharmacy|bank"](around:{SURROUND_RADIUS},{clat},{clon});'
                )
                surround_query_parts.append(
                    f'node["highway"~"bus_stop|platform"](around:{SURROUND_RADIUS},{clat},{clon});'
                )
                surround_query_parts.append(
                    f'way["highway"~"primary|secondary|tertiary|trunk|motorway"](around:{SURROUND_RADIUS},{clat},{clon});'
                )

            batch_query = (
                f'[out:json][timeout:30];\n('
                + '\n'.join(surround_query_parts)
                + '\n);\nout center;'
            )
            surround_raw = self._query_overpass(batch_query, timeout=30)
            surround_elements = surround_raw.get('elements', [])

            # Map each element to all parcels whose centroid is ≤ SURROUND_RADIUS away
            for feat in features:
                clat = feat['properties']['centroid_lat']
                clon = feat['properties']['centroid_lon']
                counts = {
                    'schools': 0,
                    'hospitals': 0,
                    'restaurants': 0,
                    'pharmacies': 0,
                    'bus_stops': 0,
                    'major_roads': 0,
                    'banks': 0,
                }
                for el in surround_elements:
                    el_tags = el.get('tags', {})
                    el_lat = el.get('lat') or (el.get('center') or {}).get('lat')
                    el_lon = el.get('lon') or (el.get('center') or {}).get('lon')
                    if el_lat is None or el_lon is None:
                        continue
                    # Quick distance check (equirectangular)
                    dlat = (el_lat - clat) * 111320
                    dlon = (el_lon - clon) * 111320 * abs(math.cos(math.radians(clat)))
                    dist = math.sqrt(dlat ** 2 + dlon ** 2)
                    if dist > SURROUND_RADIUS:
                        continue
                    amenity = el_tags.get('amenity', '')
                    highway = el_tags.get('highway', '')
                    if amenity in ('school', 'college', 'university'):
                        counts['schools'] += 1
                    elif amenity in ('hospital', 'clinic', 'doctors'):
                        counts['hospitals'] += 1
                    elif amenity in ('restaurant', 'cafe', 'fast_food'):
                        counts['restaurants'] += 1
                    elif amenity == 'pharmacy':
                        counts['pharmacies'] += 1
                    elif amenity == 'bank':
                        counts['banks'] += 1
                    elif highway in ('bus_stop', 'platform'):
                        counts['bus_stops'] += 1
                    elif highway in ('primary', 'secondary', 'tertiary', 'trunk', 'motorway'):
                        counts['major_roads'] += 1
                feat['properties']['surroundings'] = counts

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
