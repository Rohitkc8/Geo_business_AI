import os
import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.dummy import DummyClassifier
from sklearn.metrics import classification_report, multilabel_confusion_matrix
import warnings
warnings.filterwarnings('ignore')

def train_model():
    dataset_path = os.path.join(os.path.dirname(__file__), 'data', 'training', 'land_business_dataset.csv')
    models_dir = os.path.join(os.path.dirname(__file__), 'models')
    os.makedirs(models_dir, exist_ok=True)
    
    print("Loading dataset...")
    if not os.path.exists(dataset_path):
        print(f"Dataset not found at {dataset_path}")
        return
        
    df = pd.read_csv(dataset_path)
    print(f"Loaded {len(df)} samples.")
    
    # 1. Preprocessing
    features = [
        'population', 
        'population_density', 
        'residential_density', 
        'road_density', 
        'distance_to_major_road'
    ]
    
    targets = [
        'has_restaurant', 
        'has_pharmacy', 
        'has_bank', 
        'has_grocery', 
        'has_clinic'
    ]
    
    # Handle missing values
    df[features] = df[features].fillna(0)
    
    X = df[features]
    y = df[targets]
    
    # Class Balance Analysis
    print("\n--- Class Balance ---")
    for t in targets:
        print(f"{t}: {y[t].sum()} positive examples")
        
    # Spatially Aware Validation Note:
    # In a full-scale dataset, we would use spatial cross-validation (e.g. blocking by geographic coordinates)
    # to avoid data leakage between adjacent cells. Here we use standard train_test_split due to tiny sample size.
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 2. Transparent Baseline
    # A simple baseline predicting the most frequent combination
    print("\n--- Training Transparent Baseline (Dummy) ---")
    baseline = DummyClassifier(strategy='prior')
    baseline.fit(X_train_scaled, y_train)
    y_pred_base = baseline.predict(X_test_scaled)
    # For dummy, it might just predict all 1s or all 0s for each label
    print("Baseline Classification Report:")
    print(classification_report(y_test, y_pred_base, target_names=targets, zero_division=0))
    
    # 3. Train Random Forest (Justified: Non-linear feature interactions, handles multi-label naturally)
    print("\n--- Training Random Forest Classifier ---")
    rf = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
    rf.fit(X_train_scaled, y_train)
    
    y_pred_rf = rf.predict(X_test_scaled)
    
    # 4. Evaluation
    print("Random Forest Classification Report:")
    print(classification_report(y_test, y_pred_rf, target_names=targets, zero_division=0))
    
    print("\nMulti-label Confusion Matrices (RF):")
    mcm = multilabel_confusion_matrix(y_test, y_pred_rf)
    for idx, t in enumerate(targets):
        print(f"\n{t}:")
        print(mcm[idx])
        
    # Feature Importance
    print("\n--- Feature Importance ---")
    importances = rf.feature_importances_
    feat_imp = sorted(zip(features, importances), key=lambda x: x[1], reverse=True)
    for f, imp in feat_imp:
        print(f"{f}: {imp:.4f}")
        
    # 5. Save Artifacts
    model_path = os.path.join(models_dir, 'land_business_model.pkl')
    pipeline_data = {
        'model': rf,
        'scaler': scaler,
        'features': features,
        'targets': targets,
        'metadata': {
            'algorithm': 'RandomForestClassifier',
            'train_samples': len(X_train),
            'test_samples': len(X_test)
        }
    }
    
    joblib.dump(pipeline_data, model_path)
    print(f"\nModel and preprocessing pipeline saved to {model_path}")

if __name__ == "__main__":
    train_model()
