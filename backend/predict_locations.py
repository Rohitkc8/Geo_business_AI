import os
import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from feature_engineer import SpatialFeatureEngineer
from generate_dataset import generate_grid

def predict_best_locations(business_type, start_lat, start_lon, steps=2, step_size=0.01):
    """
    Given a target business type and a geographic bounding area (defined by grid),
    returns a ranked list of candidate locations from best to worst based on predicted demand.
    """
    print(f"--- Predicting Optimal Locations for {business_type.upper()} ---")
    
    models_dir = os.path.join(os.path.dirname(__file__), 'models')
    model_pkl = os.path.join(models_dir, 'business_location_model.pkl')
    pipeline_pkl = os.path.join(models_dir, 'business_location_pipeline.pkl')
    
    if not os.path.exists(model_pkl) or not os.path.exists(pipeline_pkl):
        print("Model or pipeline missing. Please train the model first.")
        return
        
    # Load model and pipeline
    model = joblib.load(model_pkl)
    
    metadata = joblib.load(pipeline_pkl)
    scaler = metadata['scaler']
    features = metadata['features']
    
    # Generate geographic candidate cells
    points = generate_grid(start_lat, start_lon, steps, steps, step_size)
    print(f"Generated {len(points)} candidate locations to evaluate.\n")
    
    engineer = SpatialFeatureEngineer()
    candidates = []
    
    for idx, (lat, lon) in enumerate(points):
        try:
            fv = engineer.generate_features(lat, lon, radius=500, competitor_category=business_type)
            
            # Extract features safely
            spatial = fv['spatial_metrics']
            counts = fv['amenity_counts']
            
            input_data = {
                'school_count': counts['school_count'],
                'college_count': counts['college_count'],
                'hospital_count': counts['hospital_count'],
                'bus_stop_count': counts['bus_stop_count'],
                'road_density': spatial['road_density_km_per_sqkm'],
                'distance_to_major_road': spatial['distance_to_major_road_meters']
            }
            
            df_input = pd.DataFrame([input_data])[features]
            X_scaled = scaler.transform(df_input)
            
            predicted_score = model.predict(X_scaled)[0]
            
            candidates.append({
                'lat': lat,
                'lon': lon,
                'predicted_demand_score': predicted_score,
                'details': input_data
            })
            
        except Exception as e:
            pass # Skip failed fetches
            
    if not candidates:
        print("Failed to evaluate any candidates.")
        return
        
    # Rank candidates by predicted demand score
    candidates_ranked = sorted(candidates, key=lambda x: x['predicted_demand_score'], reverse=True)
    
    print("=== TOP RECOMMENDED LOCATIONS ===")
    for rank, cand in enumerate(candidates_ranked, 1):
        print(f"Rank {rank}: Lat {cand['lat']:.4f}, Lon {cand['lon']:.4f}")
        print(f"   Predicted Demand Score: {cand['predicted_demand_score']:.2f}")
        
    return candidates_ranked

if __name__ == "__main__":
    # Test the inference script on a small grid around Coimbatore
    predict_best_locations(business_type='pharmacy', start_lat=11.00, start_lon=76.96, steps=2)
