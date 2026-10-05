import json
from explainability import explain_land_to_business, explain_business_to_land
from api_models import _get_input_features

def run_tests():
    print("Fetching features for a test location (Coimbatore center)...")
    lat, lon = 11.0168, 76.9558
    df = _get_input_features(lat, lon, radius=500)
    
    print("\n--- Testing LAND -> BUSINESS Explanations ---")
    results = explain_land_to_business(df)
    
    for r in results:
        print(f"\n{r['business']} — {r['score_percent']}%")
        print("Positive:")
        for pf in r['positive_factors']:
            print(f"  {pf}")
        print("Negative:")
        for nf in r['negative_factors']:
            print(f"  {nf}")

    print("\n--- Testing BUSINESS -> LAND Explanations ---")
    result_bl = explain_business_to_land(df)
    print(f"\nPharmacy Demand Score: {result_bl['predicted_demand_score']:.2f}")
    print("Positive Factors:")
    for pf in result_bl['positive_factors']:
        print(f"  {pf}")
    print("Negative Factors:")
    for nf in result_bl['negative_factors']:
        print(f"  {nf}")

if __name__ == "__main__":
    run_tests()
