import json
import urllib.error

import pytest
from fastapi import HTTPException

import main


class Response:
    def __init__(self, payload): self.payload = payload
    def read(self): return json.dumps(self.payload).encode()
    def __enter__(self): return self
    def __exit__(self, *_): return False


def test_valid_location_is_cached(monkeypatch):
    main.geocode_cache.clear()
    monkeypatch.setattr(main.urllib.request, "urlopen", lambda *_args, **_kwargs: Response([{"lat": "11.0", "lon": "76.0", "display_name": "Test place"}]))
    result = main.geocode(main.GeocodeRequest(query=" Test place "))
    assert (result.latitude, result.longitude, result.display_name) == (11.0, 76.0, "Test place")
    assert main.geocode(main.GeocodeRequest(query="Test place")) == result


def test_empty_or_unknown_location_has_meaningful_error(monkeypatch):
    with pytest.raises(HTTPException, match="Query cannot be empty"):
        main.geocode(main.GeocodeRequest(query="   "))
    monkeypatch.setattr(main.urllib.request, "urlopen", lambda *_args, **_kwargs: Response([]))
    with pytest.raises(HTTPException, match="Location not found"):
        main.geocode(main.GeocodeRequest(query="does-not-exist"))


def test_geocoding_provider_failure_has_meaningful_error(monkeypatch):
    monkeypatch.setattr(main.urllib.request, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(urllib.error.URLError("offline")))
    with pytest.raises(HTTPException, match="Failed to geocode location"):
        main.geocode(main.GeocodeRequest(query="Coimbatore"))
