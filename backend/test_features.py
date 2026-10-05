from feature_engineer import SpatialFeatureEngineer
import json

def run_tests():
    engineer = SpatialFeatureEngineer()
    
    print("--- Test 1: Feature Vector for RS Puram, Coimbatore (Restaurant Competitors) ---")
    lat1, lon1 = 11.0080177, 76.9501661
    result1 = engineer.generate_features(lat1, lon1, radius=500, competitor_category='restaurant')
    print(json.dumps(result1, indent=2))
    print()

    print("--- Test 2: Feature Vector for Tiruchirappalli (Pharmacy Competitors) ---")
    lat2, lon2 = 10.805, 78.6856
    result2 = engineer.generate_features(lat2, lon2, radius=500, competitor_category='pharmacy')
    print(json.dumps(result2, indent=2))
    print()

if __name__ == "__main__":
    run_tests()
