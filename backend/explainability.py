import os
import joblib
import pandas as pd
import numpy as np
import shap

# Cache models so we don't load them on every API request
_MODELS = {}

def load_models():
    if _MODELS:
        return
        
    models_dir = os.path.join(os.path.dirname(__file__), 'models')
    
    # 1. Land -> Business Model (Random Forest Multi-label)
    lb_path = os.path.join(models_dir, 'land_business_model.pkl')
    if os.path.exists(lb_path):
        _MODELS['land_business'] = joblib.load(lb_path)
        
    # 2. Business -> Land Model (Gradient Boosting Regressor)
    bl_model_path = os.path.join(models_dir, 'business_location_model.pkl')
    bl_pipe_path = os.path.join(models_dir, 'business_location_pipeline.pkl')
    
    if os.path.exists(bl_model_path) and os.path.exists(bl_pipe_path):
        _MODELS['business_land_model'] = joblib.load(bl_model_path)
        _MODELS['business_land_pipe'] = joblib.load(bl_pipe_path)

def generate_human_readable_explanation(feature_name, shap_value, feature_val_scaled, is_positive):
    """ Converts a SHAP attribution into a human readable +/- point. """
    # Direction of the actual feature relative to its mean
    # Since it's standard scaled, > 0 means above average
    magnitude = "high" if feature_val_scaled > 0.5 else ("moderate" if feature_val_scaled > -0.5 else "low")
    
    clean_name = feature_name.replace('_', ' ')
    
    if is_positive:
        return f"+ {magnitude} {clean_name}"
    else:
        return f"- {magnitude} {clean_name}"

def explain_land_to_business(input_features_df):
    """
    Returns predictions and explanations for a given land parcel using the RF model.
    """
    load_models()
    pipeline = _MODELS.get('land_business')
    if not pipeline:
        raise ValueError("Land->Business model not trained.")
        
    model = pipeline['model']
    scaler = pipeline['scaler']
    features = pipeline['features']
    targets = pipeline['targets']
    
    X_scaled = scaler.transform(input_features_df[features])
    
    # Predict probabilities
    probs = model.predict_proba(X_scaled) # List of arrays for multi-label
    
    # SHAP Explainer
    # TreeExplainer works natively with RandomForest
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_scaled) # List of shape (n_samples, n_features) per target
    
    results = []
    
    for i, target in enumerate(targets):
        prob = probs[i][0][1] # Probability of class 1
        score_pct = int(prob * 100)
        
        # shap_values[i] corresponds to the i-th target.
        # For a single sample, shap_values[i][0] is an array of feature contributions
        # Wait, for scikit-learn RF binary classification, shap_values[i] is a list of [negative_class_shap, positive_class_shap].
        # So we want shap_values[i][1][0] for the positive class contributions of the first sample.
        
        # Handle SHAP output format inconsistencies across versions/models
        if isinstance(shap_values, list):
            if i < len(shap_values):
                target_shap = shap_values[i]
            else:
                target_shap = shap_values[0] # Fallback
        else:
            # If shap returns a single array, it's aggregated or single output
            target_shap = shap_values
            
        if isinstance(target_shap, list) and len(target_shap) >= 2:
            contributions = target_shap[1][0]
        else:
            # Depending on shap version, it might be an array of shape (samples, features, classes)
            if len(target_shap.shape) == 3:
                contributions = target_shap[0, :, 1]
            else:
                contributions = target_shap[0]
            
        # Pair features with contributions
        feat_contrib = list(zip(features, contributions, X_scaled[0]))
        
        # Sort by absolute contribution to find top drivers
        feat_contrib.sort(key=lambda x: abs(x[1]), reverse=True)
        
        positive_factors = []
        negative_factors = []
        
        for feat_name, contrib, scaled_val in feat_contrib:
            if abs(contrib) < 0.01: # ignore noise
                continue
            if contrib > 0 and len(positive_factors) < 3:
                positive_factors.append(generate_human_readable_explanation(feat_name, contrib, scaled_val, True))
            elif contrib < 0 and len(negative_factors) < 3:
                negative_factors.append(generate_human_readable_explanation(feat_name, contrib, scaled_val, False))
                
        results.append({
            "business": target.replace('has_', '').capitalize(),
            "score_percent": score_pct,
            "positive_factors": positive_factors,
            "negative_factors": negative_factors
        })
        
    # Sort by score descending
    results.sort(key=lambda x: x['score_percent'], reverse=True)
    return results

def explain_business_to_land(input_features_df):
    """
    Returns predictions and explanations for a candidate location for Business->Land model.
    """
    load_models()
    model = _MODELS.get('business_land_model')
    pipe = _MODELS.get('business_land_pipe')
    if not model or not pipe:
        raise ValueError("Business->Land model not trained.")
        
    scaler = pipe['scaler']
    features = pipe['features']
    
    X_scaled = scaler.transform(input_features_df[features])
    
    # Predict Demand Score
    score = model.predict(X_scaled)[0]
    
    # SHAP Explainer
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_scaled) # Shape: (n_samples, n_features)
    contributions = shap_values[0]
    
    feat_contrib = list(zip(features, contributions, X_scaled[0]))
    feat_contrib.sort(key=lambda x: abs(x[1]), reverse=True)
    
    positive_factors = []
    negative_factors = []
    
    for feat_name, contrib, scaled_val in feat_contrib:
        if abs(contrib) < 0.01:
            continue
        if contrib > 0 and len(positive_factors) < 3:
            positive_factors.append(generate_human_readable_explanation(feat_name, contrib, scaled_val, True))
        elif contrib < 0 and len(negative_factors) < 3:
            negative_factors.append(generate_human_readable_explanation(feat_name, contrib, scaled_val, False))
            
    return {
        "predicted_demand_score": float(score),
        "positive_factors": positive_factors,
        "negative_factors": negative_factors
    }
