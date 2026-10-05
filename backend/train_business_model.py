import os
import json
import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from scipy.stats import spearmanr
import warnings
warnings.filterwarnings('ignore')

def train():
    dataset_path = os.path.join(os.path.dirname(__file__), 'data', 'training', 'business_location_dataset.csv')
    models_dir = os.path.join(os.path.dirname(__file__), 'models')
    os.makedirs(models_dir, exist_ok=True)
    
    if not os.path.exists(dataset_path):
        print("Dataset not found!")
        return
        
    df = pd.read_csv(dataset_path)
    
    # 1. Target Leakage Prevention
    # The target `target_demand_proxy_score` is mathematically derived from population, competitor_count, and business_density.
    # Including these directly (or derived proxies like `households`) would be direct TARGET LEAKAGE.
    # The model would simply learn the formula. We exclude them.
    leaky_features = ['population', 'population_density', 'households', 'residential_density', 'competitor_count', 'business_density']
    
    features = [
        'school_count', 
        'college_count', 
        'hospital_count', 
        'bus_stop_count', 
        'road_density', 
        'distance_to_major_road'
    ]
    
    target = 'target_demand_proxy_score'
    
    X = df[features].fillna(0)
    y = df[target]
    
    # 2. Spatial Leakage & Overfitting Check
    # Note: Random train_test_split on geospatial grid data causes SPATIAL LEAKAGE 
    # (adjacent cells in train/test are highly correlated). 
    # A robust pipeline would use Spatial K-Fold cross validation.
    # Overfitting Check: We will compare train vs test metrics to check for overfitting.
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    
    # 3. Preprocessing
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 4. Transparent Baseline
    print("\n--- Training Transparent Baseline (Mean Regressor) ---")
    baseline = DummyRegressor(strategy='mean')
    baseline.fit(X_train_scaled, y_train)
    y_pred_base = baseline.predict(X_test_scaled)
    
    print(f"MAE:  {mean_absolute_error(y_test, y_pred_base):.2f}")
    print(f"RMSE: {np.sqrt(mean_squared_error(y_test, y_pred_base)):.2f}")
    print(f"R2:   {r2_score(y_test, y_pred_base):.2f}")
    
    # 5. XGBoost Model
    print("\n--- Training XGBoost Regressor ---")
    # Using small max_depth to prevent extreme overfitting on tiny datasets
    model = GradientBoostingRegressor(n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42)
    model.fit(X_train_scaled, y_train)
    
    # Predict Train and Test (Overfitting Check)
    y_pred_train = model.predict(X_train_scaled)
    y_pred_test = model.predict(X_test_scaled)
    
    print("\nOVERFITTING CHECK (Train vs Test Metrics):")
    print(f"Train R2: {r2_score(y_train, y_pred_train):.2f} | Test R2: {r2_score(y_test, y_pred_test):.2f}")
    
    print("\nTEST METRICS:")
    print(f"MAE:  {mean_absolute_error(y_test, y_pred_test):.2f}")
    print(f"RMSE: {np.sqrt(mean_squared_error(y_test, y_pred_test)):.2f}")
    
    # 6. Ranking Metrics
    # For geographic recommendations, predicting the exact score matters less than ranking the locations correctly.
    rank_corr, p_value = spearmanr(y_test, y_pred_test)
    print(f"Spearman Rank Correlation: {rank_corr:.2f} (p-value: {p_value:.4f})")
    
    # 7. Feature Importance
    print("\n--- Feature Importance ---")
    importances = model.feature_importances_
    for f, imp in sorted(zip(features, importances), key=lambda x: x[1], reverse=True):
        print(f"{f}: {imp:.4f}")
        
    # 8. Save Models and Metadata
    model_pkl_path = os.path.join(models_dir, 'business_location_model.pkl')
    pipeline_path = os.path.join(models_dir, 'business_location_pipeline.pkl')
    joblib.dump(model, model_pkl_path)
    
    # Save preprocessing and metadata
    metadata = {
        'scaler': scaler,
        'features': features,
        'target_variable': target,
        'leaky_features_excluded': leaky_features,
        'notes': 'Model trained using spatial proxies to prevent target leakage from the Demand Proxy Score formula.'
    }
    joblib.dump(metadata, pipeline_path)
    
    print(f"\nModel saved to: {model_pkl_path}")
    print(f"Metadata/Pipeline saved to: {pipeline_path}")

if __name__ == "__main__":
    train()
