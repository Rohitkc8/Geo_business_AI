import json
from api_routes import (
    get_business_types,
    get_location_details,
    get_map_data,
    analyze_location,
    find_best_locations,
    AnalyzeLocationRequest,
    FindBestLocationsRequest
)

def test_api():
    print("\n--- Testing GET /api/business-types ---")
    print(get_business_types())
    
    # RS Puram coordinates
    lat = 11.0080
    lon = 76.9501
    
    print("\n--- Testing GET /api/location-details ---")
    details = get_location_details(lat, lon, 500)
    print(f"Population: {details['population_metrics']['population']}")
    print(f"Business Count: {details['spatial_metrics']['business_density_per_sqkm']}")
    
    print("\n--- Testing GET /api/map-data ---")
    map_data = get_map_data(lat, lon, 500)
    print(f"Returned {len(map_data['features'])} raw geographic features for the map.")
    
    print("\n--- Testing POST /api/analyze-location ---")
    req = AnalyzeLocationRequest(lat=lat, lon=lon, radius=500)
    analysis = analyze_location(req)
    print(f"Analyzed {lat}, {lon}. Top recommendation:")
    print(json.dumps(analysis['recommendations'][0], indent=2))
    
    print("\n--- Testing POST /api/find-best-locations ---")
    # One cached real-data cell makes this smoke test deterministic and avoids
    # depending on a live Overpass request during local test runs.
    req2 = FindBestLocationsRequest(business_type='pharmacy', start_lat=11.01, start_lon=76.95, steps=1, step_size=0.01)
    best_locs = find_best_locations(req2)
    print(f"Found {len(best_locs['candidates'])} candidates.")
    print("Top Candidate:")
    candidate = best_locs['candidates'][0]
    assert candidate['model_score'] == candidate['score']
    assert candidate['details']['competitors'] >= 0
    print(json.dumps(candidate, indent=2))
    print("Test Complete!")

if __name__ == "__main__":
    test_api()
