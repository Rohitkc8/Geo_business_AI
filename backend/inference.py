import os
import joblib
import pandas as pd
from feature_engineer import SpatialFeatureEngineer
import warnings
warnings.filterwarnings('ignore')

def run_inference(lat, lon, radius=500):
    models_dir = os.path.join(os.path.dirname(__file__), 'models')
    model_path = os.path.join(models_dir, 'land_business_model.pkl')
    
    if not os.path.exists(model_path):
        print("Model not found. Train the model first.")
        return
        
    # Load pipeline
    pipeline_data = joblib.load(model_path)
    model = pipeline_data['model']
    scaler = pipeline_data['scaler']
    features = pipeline_data['features']
    targets = pipeline_data['targets']
    
    print(f"\n--- Running Inference for Lat: {lat}, Lon: {lon} ---")
    print("Generating spatial features...")
    engineer = SpatialFeatureEngineer()
    fv = engineer.generate_features(lat, lon, radius=radius)
    
    # Extract needed features
    pop_metrics = fv['population_metrics']
    spatial = fv['spatial_metrics']
    
    input_data = {
        'population': pop_metrics['population'] if pop_metrics['population'] is not None else 0,
        'population_density': pop_metrics['population_density'] if pop_metrics['population_density'] is not None else 0,
        'residential_density': pop_metrics['residential_density'] if pop_metrics['residential_density'] is not None else 0,
        'road_density': spatial['road_density_km_per_sqkm'],
        'distance_to_major_road': spatial['distance_to_major_road_meters']
    }
    
    # Create DataFrame for scaling
    df_input = pd.DataFrame([input_data])[features]
    
    # Scale
    X_scaled = scaler.transform(df_input)
    
    # Predict
    preds = model.predict(X_scaled)[0]
    
    # Because predict_proba is a list of arrays for multi-label, we can extract probabilities:
    probs = model.predict_proba(X_scaled)
    # probs is a list of length n_targets, each is an array of shape (1, 2)
    
    print("\n--- Predictions ---")
    for i, target in enumerate(targets):
        prob_positive = probs[i][0][1]
        prediction = bool(preds[i])
        
        status = "RECOMMENDED" if prediction else "NOT RECOMMENDED"
        print(f"{target.replace('has_', '').upper():<15}: {status:<15} (Confidence: {prob_positive*100:.1f}%)")

if __name__ == "__main__":
    # Test on an unseen location (e.g. Bangalore center)
    test_lat, test_lon = 12.9716, 77.5946
    run_inference(test_lat, test_lon, radius=500)
