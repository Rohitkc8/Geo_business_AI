import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def feature_vector():
    return {
        "population_metrics": {"population": 1200, "population_density": 1200, "residential_density": 300},
        "amenity_counts": {"school_count": 2, "college_count": 1, "hospital_count": 1, "bus_stop_count": 4, "pharmacy_count": 2},
        "spatial_metrics": {"road_density_km_per_sqkm": 12, "distance_to_major_road_meters": 80},
        "features": [{"id": "node/1", "name": "Test school", "category": "education", "latitude": 11.0, "longitude": 76.0, "tags": {"amenity": "school"}}],
    }
