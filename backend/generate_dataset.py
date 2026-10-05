import os
import csv
import pandas as pd
import time
from feature_engineer import SpatialFeatureEngineer

TRAIN_DIR = os.path.join(os.path.dirname(__file__), 'data', 'training')
os.makedirs(TRAIN_DIR, exist_ok=True)
DATASET_PATH = os.path.join(TRAIN_DIR, 'land_business_dataset.csv')

def generate_grid(start_lat, start_lon, steps_lat, steps_lon, step_size_deg=0.01):
    grid = []
    for i in range(steps_lat):
        for j in range(steps_lon):
            grid.append((start_lat + i * step_size_deg, start_lon + j * step_size_deg))
    return grid

def generate_dataset():
    engineer = SpatialFeatureEngineer()
    
    # Generate a 2x2 grid around Coimbatore (~4 samples) to demonstrate pipeline quickly
    # 0.01 deg is approx 1.1km. Radius of 500m per cell ensures minimal overlap.
    points = generate_grid(10.99, 76.94, 2, 2, 0.01)
    
    rows = []
    print(f"Generating dataset for {len(points)} geographic cells...")
    
    for idx, (lat, lon) in enumerate(points):
        print(f"[{idx+1}/{len(points)}] Processing cell at {lat:.4f}, {lon:.4f}...")
        try:
            fv = engineer.generate_features(lat, lon, radius=500, competitor_category='restaurant')
            
            # Features
            pop_metrics = fv['population_metrics']
            spatial = fv['spatial_metrics']
            counts = fv['amenity_counts']
            
            row = {
                'lat': lat,
                'lon': lon,
                'population': pop_metrics['population'] if pop_metrics['population'] is not None else 0,
                'population_density': pop_metrics['population_density'] if pop_metrics['population_density'] is not None else 0,
                'residential_density': pop_metrics['residential_density'] if pop_metrics['residential_density'] is not None else 0,
                'road_density': spatial['road_density_km_per_sqkm'],
                'distance_to_major_road': spatial['distance_to_major_road_meters'],
                'total_businesses': sum(counts.values()),
                
                # Targets (Multi-label)
                'has_restaurant': 1 if counts['restaurant_count'] > 0 else 0,
                'has_pharmacy': 1 if counts['pharmacy_count'] > 0 else 0,
                'has_bank': 1 if counts['bank_count'] > 0 else 0,
                'has_grocery': 1 if counts['grocery_count'] > 0 else 0,
                'has_clinic': 1 if counts['clinic_count'] > 0 else 0
            }
            rows.append(row)
            
            # Rate limiting sleep to respect Overpass and WorldPop
            time.sleep(1)
        except Exception as e:
            print(f"Error processing {lat},{lon}: {e}")
            
    # Save to CSV
    df = pd.DataFrame(rows)
    df.to_csv(DATASET_PATH, index=False)
    print(f"\nDataset saved to {DATASET_PATH}")
    
    # Dataset Report
    print("\n" + "="*40)
    print("DATASET REPORT")
    print("="*40)
    print(f"Total samples: {len(df)}")
    
    print("\n--- Missing Values ---")
    print(df.isnull().sum())
    
    print("\n--- Duplicates ---")
    print(f"Duplicate rows: {df.duplicated(subset=['lat', 'lon']).sum()}")
    
    print("\n--- Class Balance (Targets) ---")
    targets = ['has_restaurant', 'has_pharmacy', 'has_bank', 'has_grocery', 'has_clinic']
    for t in targets:
        positive = df[t].sum()
        print(f"{t}: {positive} positive ({positive/len(df)*100:.1f}%)")
        
    print("\n--- Feature Distributions (Outliers Check) ---")
    features = ['population', 'population_density', 'road_density', 'distance_to_major_road']
    print(df[features].describe().T[['min', 'mean', '50%', 'max']])
    print("="*40)

if __name__ == "__main__":
    generate_dataset()
