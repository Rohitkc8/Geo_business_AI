import os
import math
import pandas as pd
from feature_engineer import SpatialFeatureEngineer
from generate_dataset import generate_grid

TRAIN_DIR = os.path.join(os.path.dirname(__file__), 'data', 'training')
os.makedirs(TRAIN_DIR, exist_ok=True)
DATASET_PATH = os.path.join(TRAIN_DIR, 'business_location_dataset.csv')

def calculate_demand_proxy_score(population, competitor_count, business_density):
    # DPS = ((Pop + 1) / (Competitors + 1)) * log10(BusinessDensity + 10)
    # A mathematically sound proxy for underserved commercial areas
    pop_safe = (population or 0) + 1
    comp_safe = (competitor_count or 0) + 1
    biz_safe = (business_density or 0) + 10
    
    return (pop_safe / comp_safe) * math.log10(biz_safe)

def generate_business_dataset():
    engineer = SpatialFeatureEngineer()
    
    # We will generate candidate locations for a 'pharmacy' expansion
    TARGET_BUSINESS = 'pharmacy'
    
    # 3x3 grid around Coimbatore (~9 samples) to demonstrate
    points = generate_grid(10.99, 76.94, 3, 3, 0.01)
    
    rows = []
    print(f"Generating Business->Land dataset for '{TARGET_BUSINESS}' over {len(points)} candidate locations...")
    
    for idx, (lat, lon) in enumerate(points):
        print(f"[{idx+1}/{len(points)}] Evaluating land parcel at {lat:.4f}, {lon:.4f}...")
        try:
            fv = engineer.generate_features(lat, lon, radius=500, competitor_category=TARGET_BUSINESS)
            
            pop_metrics = fv['population_metrics']
            spatial = fv['spatial_metrics']
            counts = fv['amenity_counts']
            
            # Extract values
            pop = pop_metrics['population'] if pop_metrics['population'] is not None else 0
            pop_dens = pop_metrics['population_density'] if pop_metrics['population_density'] is not None else 0
            res_dens = pop_metrics['residential_density'] if pop_metrics['residential_density'] is not None else 0
            households = pop_metrics['households'] if pop_metrics['households'] is not None else 0
            
            competitors = spatial['competitor_count']
            biz_dens = spatial['business_density_per_sqkm']
            
            # Calculate Target Score
            dps_score = calculate_demand_proxy_score(pop, competitors, biz_dens)
            
            row = {
                'lat': lat,
                'lon': lon,
                'target_business': TARGET_BUSINESS,
                
                # Features
                'population': pop,
                'population_density': pop_dens,
                'households': households,
                'residential_density': res_dens,
                'competitor_count': competitors,
                'school_count': counts['school_count'],
                'college_count': counts['college_count'],
                'hospital_count': counts['hospital_count'],
                'bus_stop_count': counts['bus_stop_count'],
                'road_density': spatial['road_density_km_per_sqkm'],
                'distance_to_major_road': spatial['distance_to_major_road_meters'],
                'business_density': biz_dens,
                
                # Target
                'target_demand_proxy_score': round(dps_score, 2)
            }
            rows.append(row)
            
        except Exception as e:
            print(f"Error processing {lat},{lon}: {e}")
            
    # Save to CSV
    df = pd.DataFrame(rows)
    df.to_csv(DATASET_PATH, index=False)
    print(f"\nDataset saved to {DATASET_PATH}")
    
    # Dataset Quality Report
    print("\n" + "="*40)
    print("DATASET QUALITY REPORT")
    print("="*40)
    print(f"Total candidate locations evaluated: {len(df)}")
    
    print("\n--- Missing Values ---")
    print(df.isnull().sum()[df.isnull().sum() > 0])
    
    print("\n--- Target Score Distribution ---")
    print(df['target_demand_proxy_score'].describe())
    
    print("\n--- Feature Analysis (Top 5 Locations by Demand Proxy) ---")
    top_5 = df.sort_values('target_demand_proxy_score', ascending=False).head(5)
    print(top_5[['lat', 'lon', 'population', 'competitor_count', 'target_demand_proxy_score']])
    print("="*40)

if __name__ == "__main__":
    generate_business_dataset()
