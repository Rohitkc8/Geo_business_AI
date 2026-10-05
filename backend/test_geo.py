from geo_service import GeoDataService

def run_test():
    service = GeoDataService()

    print("--- Test 1: RS Puram, Coimbatore ---")
    lat1, lon1 = 11.0080177, 76.9501661
    result1 = service.get_features(lat1, lon1, radius=500)
    print(f"Total features found: {result1['summary']['total_features']}")
    print(f"Population Metrics: {result1['population_metrics']}")
    print(f"Sample features: {[f['name'] for f in result1['features'][:5]]}")
    print()

    print("--- Test 2: Tiruchirappalli Center ---")
    lat2, lon2 = 10.805, 78.6856
    result2 = service.get_features(lat2, lon2, radius=500)
    print(f"Total features found: {result2['summary']['total_features']}")
    print(f"Population Metrics: {result2['population_metrics']}")
    print(f"Sample features: {[f['name'] for f in result2['features'][:5]]}")

if __name__ == "__main__":
    run_test()
