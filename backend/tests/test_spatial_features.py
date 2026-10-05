from feature_engineer import SpatialFeatureEngineer


def test_spatial_feature_counts_and_selected_competition(monkeypatch):
    raw = {
        "population_metrics": {"population": 1000, "population_density": 1000, "area_sq_km": 1},
        "features": [
            {"tags": {"amenity": "pharmacy"}, "category": "pharmacy", "latitude": 11, "longitude": 76},
            {"tags": {"shop": "supermarket"}, "category": "grocery_store", "latitude": 11, "longitude": 76},
            {"tags": {"amenity": "school"}, "category": "education", "latitude": 11, "longitude": 76},
        ],
    }
    engineer = SpatialFeatureEngineer()
    monkeypatch.setattr(engineer.geo_service, "get_features", lambda *_args, **_kwargs: raw)
    result = engineer.generate_features(11, 76, competitor_category="pharmacy")
    assert result["amenity_counts"]["pharmacy_count"] == 1
    assert result["amenity_counts"]["grocery_count"] == 1
    assert result["spatial_metrics"]["competitor_count"] == 1


def test_spatial_provider_failure_propagates(monkeypatch):
    engineer = SpatialFeatureEngineer()
    monkeypatch.setattr(engineer.geo_service, "get_features", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("provider unavailable")))
    import pytest
    with pytest.raises(RuntimeError, match="provider unavailable"):
        engineer.generate_features(11, 76)
