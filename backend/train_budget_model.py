import os
import joblib
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

def train_budget_model():
    print("Generating synthetic data for budget model...")
    # Features: population_density, distance_to_major_road, school_count, hospital_count
    np.random.seed(42)
    n_samples = 1000
    
    pop_density = np.random.uniform(0, 5000, n_samples)
    road_dist = np.random.uniform(0, 2000, n_samples)
    schools = np.random.randint(0, 10, n_samples)
    hospitals = np.random.randint(0, 5, n_samples)
    
    # Synthetic logic for target (budget per cent in INR)
    # Base: 5,00,000
    # Density: +150 per pop_density
    # Road: -100 per meter distance
    # Schools: +20,000 per school
    # Hospitals: +50,000 per hospital
    
    base_price = 500000
    target_price = (
        base_price 
        + (pop_density * 150) 
        - (road_dist * 100)
        + (schools * 20000)
        + (hospitals * 50000)
        + np.random.normal(0, 50000, n_samples) # Add some noise
    )
    # Ensure minimum price
    target_price = np.maximum(target_price, 100000)
    
    df = pd.DataFrame({
        'population_density': pop_density,
        'distance_to_major_road': road_dist,
        'school_count': schools,
        'hospital_count': hospitals,
        'price_per_cent': target_price
    })
    
    X = df[['population_density', 'distance_to_major_road', 'school_count', 'hospital_count']]
    y = df['price_per_cent']
    
    model = RandomForestRegressor(n_estimators=50, random_state=42)
    model.fit(X, y)
    
    models_dir = os.path.join(os.path.dirname(__file__), 'models')
    os.makedirs(models_dir, exist_ok=True)
    
    model_path = os.path.join(models_dir, 'budget_model.pkl')
    joblib.dump(model, model_path)
    print(f"Model saved to {model_path}")

if __name__ == "__main__":
    train_budget_model()
