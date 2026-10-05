import math
from geo_service import GeoDataService

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000 # Radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

class SpatialFeatureEngineer:
    def __init__(self):
        self.geo_service = GeoDataService()

    def generate_features(self, lat: float, lon: float, radius: int = 1000, competitor_category: str = 'restaurant'):
        """
        Generate a structured feature vector for spatial analysis.
        """
        # 1. Fetch raw data
        geo_data = self.geo_service.get_features(lat, lon, radius)
        features = geo_data.get('features', [])
        pop_metrics = geo_data.get('population_metrics', {})
        
        # 2. Extract Population Features
        population = pop_metrics.get('population') or 0
        area_sq_km = pop_metrics.get('area_sq_km') or ((radius*2/1000)**2)
        population_density = pop_metrics.get('population_density') or 0
        households = pop_metrics.get('households') or (population / 4) if population else 0
        residential_density = households / area_sq_km if area_sq_km > 0 else 0

        # 3. Categorize counts
        counts = {
            'school_count': 0,
            'college_count': 0,
            'hospital_count': 0,
            'clinic_count': 0,
            'bus_stop_count': 0,
            'grocery_count': 0,
            'pharmacy_count': 0,
            'restaurant_count': 0,
            'cafe_count': 0,
            'bank_count': 0,
            'competitor_count': 0,
            'total_businesses': 0
        }
        
        major_roads = []

        for f in features:
            tags = f.get('tags', {})
            cat = f.get('category', '')
            amenity = tags.get('amenity', '')
            shop = tags.get('shop', '')
            highway = tags.get('highway', '')
            
            # Identify specific counts
            if amenity == 'school': counts['school_count'] += 1
            if amenity in ['college', 'university']: counts['college_count'] += 1
            if amenity == 'hospital': counts['hospital_count'] += 1
            if amenity in ['clinic', 'doctors']: counts['clinic_count'] += 1
            if highway in ['bus_stop', 'platform'] or cat == 'bus_stop': counts['bus_stop_count'] += 1
            if shop in ['supermarket', 'convenience', 'grocery']: counts['grocery_count'] += 1
            if amenity == 'pharmacy': counts['pharmacy_count'] += 1
            if amenity in ['restaurant', 'fast_food']: counts['restaurant_count'] += 1
            if amenity == 'cafe': counts['cafe_count'] += 1
            if amenity == 'bank': counts['bank_count'] += 1
            
            # Any shop, office, or amenity counts as a business
            if 'shop' in tags or 'office' in tags or amenity in ['restaurant', 'cafe', 'fast_food', 'bank', 'pharmacy']:
                counts['total_businesses'] += 1
                
                
            if highway in ['primary', 'secondary', 'trunk', 'motorway']:
                major_roads.append(f)

        # Competition is the count for the selected business category.  Use the
        # specialised counts rather than the display category so grocery shops
        # and restaurant fast-food variants are included consistently.
        category_count_key = f'{competitor_category}_count'
        counts['competitor_count'] = counts.get(category_count_key, 0)

        # 4. Advanced Spatial Metrics (Distance & Density)
        business_density = counts['total_businesses'] / area_sq_km if area_sq_km > 0 else 0
        
        distance_to_major_road = -1 # -1 implies not found within radius
        if major_roads:
            distances = [haversine_distance(lat, lon, r['latitude'], r['longitude']) for r in major_roads if r.get('latitude')]
            if distances:
                distance_to_major_road = min(distances)
                
        # Try to use OSMnx for actual road length density if installed, otherwise fallback
        road_density = 0
        try:
            import osmnx as ox
            import networkx as nx
            # Fetch graph within radius
            # Setting simplify=True to just get road network lengths
            ox.settings.log_console = False
            ox.settings.use_cache = True
            G = ox.graph_from_point((lat, lon), dist=radius, network_type='drive')
            
            total_length_m = sum([d['length'] for u, v, d in G.edges(data=True) if 'length' in d])
            # Density as km of road per sq km
            road_density = (total_length_m / 1000.0) / area_sq_km
        except Exception as e:
            # Fallback: estimate road density as count of highway nodes/ways per sq km
            highway_count = sum(1 for f in features if 'highway' in f.get('tags', {}))
            road_density = highway_count / area_sq_km if area_sq_km > 0 else 0

        # 5. Assemble Feature Vector
        feature_vector = {
            "population_metrics": {
                "population": population,
                "population_density": round(population_density, 2),
                "households": households,
                "residential_density": round(residential_density, 2),
                "coverage_status": pop_metrics.get("coverage_status", "limited")
            },
            "amenity_counts": {
                "school_count": counts['school_count'],
                "college_count": counts['college_count'],
                "hospital_count": counts['hospital_count'],
                "clinic_count": counts['clinic_count'],
                "bus_stop_count": counts['bus_stop_count'],
                "grocery_count": counts['grocery_count'],
                "pharmacy_count": counts['pharmacy_count'],
                "restaurant_count": counts['restaurant_count'],
                "cafe_count": counts['cafe_count'],
                "bank_count": counts['bank_count']
            },
            "spatial_metrics": {
                "road_density_km_per_sqkm": round(road_density, 2),
                "distance_to_major_road_meters": round(distance_to_major_road, 2),
                "business_density_per_sqkm": round(business_density, 2),
                "competitor_count": counts['competitor_count']
            },
            "metadata": {
                "competitor_category_used": competitor_category,
                "radius_meters": radius,
                "area_sq_km": round(area_sq_km, 2)
            }
        }
        
        return feature_vector
