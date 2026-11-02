"""Optional Google Places (New) enrichment for aggregate scoring.

This module is intentionally backend-only. It returns aggregate signals and
never sends Google place records to the frontend map. Enable it by setting
GOOGLE_MAPS_API_KEY. Review Google's current terms, billing, field-mask, and
caching requirements before production use.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.request
from collections import defaultdict
from typing import Any

GOOGLE_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"

# Google types used only for classification of aggregate signals.
TYPE_TO_CATEGORY = {
    "restaurant": "restaurant",
    "cafe": "cafe",
    "pharmacy": "pharmacy",
    "bank": "bank",
    "grocery_store": "grocery",
    "supermarket": "grocery",
    "convenience_store": "grocery",
    "doctor": "clinic",
    "medical_clinic": "clinic",
    "hospital": "clinic",
}


def _empty() -> dict[str, Any]:
    return {category: {"count": 0, "open_count": 0, "rating_sum": 0.0, "rated_count": 0} for category in ("restaurant", "cafe", "pharmacy", "grocery", "bank", "clinic")}


def _primary_category(place: dict[str, Any]) -> str | None:
    primary = str(place.get("primaryType", "")).lower()
    if primary in TYPE_TO_CATEGORY:
        return TYPE_TO_CATEGORY[primary]
    for place_type in place.get("types", []) or []:
        if str(place_type).lower() in TYPE_TO_CATEGORY:
            return TYPE_TO_CATEGORY[str(place_type).lower()]
    return None


def get_google_place_signals(lat: float, lon: float, radius: int = 1000) -> dict[str, Any] | None:
    """Fetch aggregate nearby signals; return None when Google is not enabled."""
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        return None

    payload = {
        "includedTypes": ["restaurant", "cafe", "pharmacy", "grocery_store", "supermarket", "convenience_store", "bank", "doctor", "medical_clinic", "hospital"],
        "maxResultCount": 20,
        "locationRestriction": {"circle": {"center": {"latitude": float(lat), "longitude": float(lon)}, "radius": float(min(max(radius, 1), 50000))}},
    }
    # Keep the mask explicit. Add rating fields only when requested so the
    # project owner can control both cost and terms-sensitive data usage.
    field_mask = "places.primaryType,places.types,places.businessStatus"
    if os.getenv("GOOGLE_PLACES_INCLUDE_RATINGS", "true").lower() in {"1", "true", "yes"}:
        field_mask += ",places.rating,places.userRatingCount"

    request = urllib.request.Request(
        GOOGLE_NEARBY_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": field_mask,
            "User-Agent": "GeoBusinessAI/1.0",
        },
    )
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(request, timeout=8, context=ctx) as response:
        data = json.loads(response.read().decode("utf-8"))

    signals = _empty()
    for place in data.get("places", []):
        category = _primary_category(place)
        if not category:
            continue
        item = signals[category]
        item["count"] += 1
        if place.get("businessStatus", "") == "OPERATIONAL":
            item["open_count"] += 1
        if place.get("rating") is not None:
            item["rating_sum"] += float(place["rating"])
            item["rated_count"] += 1

    for item in signals.values():
        item["average_rating"] = round(item["rating_sum"] / item["rated_count"], 2) if item["rated_count"] else None
        del item["rating_sum"]
    return {"enabled": True, "source": "google_places", "radius_meters": radius, "categories": signals}
