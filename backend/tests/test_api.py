from fastapi.testclient import TestClient

import api_routes
import main
from conftest import feature_vector


client = TestClient(main.app)


def test_api_valid_land_and_business_workflows(monkeypatch):
    monkeypatch.setattr(api_routes.engineer, "generate_features", lambda *_args, **_kwargs: feature_vector())
    monkeypatch.setattr(api_routes.engineer.geo_service, "get_features", lambda *_args, **_kwargs: feature_vector())
    monkeypatch.setattr(api_routes, "explain_land_to_business", lambda _df: [{"business": "Pharmacy", "score_percent": 80, "positive_factors": [], "negative_factors": []}])
    monkeypatch.setattr(api_routes, "explain_business_to_land", lambda _df: {"predicted_demand_score": 42.5, "positive_factors": ["+ bus stops"], "negative_factors": []})
    land = client.post("/api/analyze-location", json={"lat": 11, "lon": 76, "radius": 500})
    business = client.post("/api/find-best-locations", json={"business_type": " pharmacy ", "start_lat": 11, "start_lon": 76, "steps": 1})
    assert land.status_code == 200 and land.json()["recommendations"][0]["business"] == "Pharmacy"
    assert business.status_code == 200 and business.json()["candidates"][0]["model_score"] == 42.5


def test_api_rejects_empty_business_and_invalid_radius():
    empty = client.post("/api/find-best-locations", json={"business_type": " ", "start_lat": 11, "start_lon": 76})
    radius = client.post("/api/analyze-location", json={"lat": 11, "lon": 76, "radius": 0})
    assert empty.status_code == 422 and "business_type cannot be empty" in str(empty.json())
    assert radius.status_code == 422


def test_api_returns_meaningful_provider_and_model_errors(monkeypatch):
    monkeypatch.setattr(api_routes.engineer, "generate_features", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")))
    provider = client.get("/api/location-details?lat=11&lon=76")
    assert provider.status_code == 500 and provider.json()["detail"] == "Failed to fetch location details"
    monkeypatch.setattr(api_routes, "_get_input_features", lambda *_args, **_kwargs: (None, {}))
    monkeypatch.setattr(api_routes, "explain_land_to_business", lambda *_args: (_ for _ in ()).throw(RuntimeError("model missing")))
    model = client.post("/api/analyze-location", json={"lat": 11, "lon": 76})
    assert model.status_code == 500 and model.json()["detail"] == "Model 1 inference failed"
