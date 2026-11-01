"""Transparent, category-aware business opportunity scoring.

This is intentionally used instead of the old four-row multi-label model. That
model learned whether a business already existed nearby, which is not the same
as estimating an opportunity to open one.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple


BUSINESS_TYPES = ("pharmacy", "grocery", "cafe", "restaurant", "bank", "clinic")

# Weights are deliberately conservative and explainable. Competition is a
# saturation signal: a few nearby businesses validate demand, while too many
# reduce the opportunity score.
CATEGORY_CONFIG: Dict[str, Dict[str, Any]] = {
    "restaurant": {"demand": ("population", 0.28), "access": 0.22, "support": (("bus_stop_count", 0.10), ("school_count", 0.08)), "competition": 0.32, "ideal_competition": 4},
    "cafe": {"demand": ("population", 0.22), "access": 0.24, "support": (("school_count", 0.14), ("bus_stop_count", 0.10)), "competition": 0.30, "ideal_competition": 3},
    "pharmacy": {"demand": ("population", 0.30), "access": 0.15, "support": (("hospital_count", 0.22), ("clinic_count", 0.12)), "competition": 0.30, "ideal_competition": 3},
    "clinic": {"demand": ("population", 0.28), "access": 0.15, "support": (("hospital_count", 0.18), ("pharmacy_count", 0.10)), "competition": 0.29, "ideal_competition": 2},
    "grocery": {"demand": ("population", 0.38), "access": 0.16, "support": (("bus_stop_count", 0.10), ("school_count", 0.08)), "competition": 0.28, "ideal_competition": 4},
    "bank": {"demand": ("population", 0.24), "access": 0.25, "support": (("bus_stop_count", 0.12), ("college_count", 0.10)), "competition": 0.29, "ideal_competition": 2},
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _range_score(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.5
    return _clamp((value - low) / (high - low))


def _features(df_input: Any, feature_vector: Dict[str, Any] | None) -> Dict[str, float]:
    row = df_input.iloc[0].to_dict() if hasattr(df_input, "iloc") else {}
    counts = (feature_vector or {}).get("amenity_counts", {})
    spatial = (feature_vector or {}).get("spatial_metrics", {})
    population = float(row.get("population", 0) or 0)
    density = float(row.get("population_density", population) or population)
    road_density = float(row.get("road_density", spatial.get("road_density_km_per_sqkm", 0)) or 0)
    road_distance = float(row.get("distance_to_major_road", spatial.get("distance_to_major_road_meters", -1)) or -1)
    return {
        "population": population,
        "population_density": density,
        "road_density": road_density,
        "road_access": 1.0 if road_distance < 0 else 1.0 - _clamp(road_distance / 1000.0),
        **{key: float(value or 0) for key, value in counts.items()},
    }


def score_business(business_type: str, df_input: Any, feature_vector: Dict[str, Any] | None = None) -> Tuple[float, list[str], list[str]]:
    """Return an opportunity score in [0, 100] plus human-readable drivers."""
    business = str(business_type).strip().lower().replace(" ", "_")
    if business == "grocery_store":
        business = "grocery"
    if business not in CATEGORY_CONFIG:
        business = "restaurant"
    cfg = CATEGORY_CONFIG[business]
    f = _features(df_input, feature_vector)

    demand = _range_score(f["population_density"], 500, 15000)
    access = (0.65 * f["road_access"] + 0.35 * _range_score(f["road_density"], 0, 180))
    support = sum(weight * _range_score(f.get(name, 0), 0, 10) for name, weight in cfg["support"])
    demand_component = cfg["demand"][1] * demand
    support_component = support
    access_component = cfg["access"] * access
    competitor_count = f.get(f"{business}_count", f.get("competitor_count", 0))
    ideal = float(cfg["ideal_competition"])
    # A small existing market validates demand; saturation is penalized.
    competition_score = _clamp(1.0 - max(0.0, competitor_count - ideal) / max(ideal * 2, 1))
    raw = 100 * (0.20 + demand_component + support_component + access_component + cfg["competition"] * competition_score)
    score = round(_clamp(raw, 0, 100), 1)

    positive = []
    negative = []
    if demand >= 0.55:
        positive.append("+ high population density")
    else:
        negative.append("- low population density")
    if access >= 0.55:
        positive.append("+ good road access")
    else:
        negative.append("- limited road access")
    for name, _ in cfg["support"]:
        if f.get(name, 0) > 0:
            positive.append(f"+ nearby {name.replace('_count', '').replace('_', ' ')}")
    if competitor_count > ideal * 1.5:
        negative.append(f"- high {business} competition ({int(competitor_count)})")
    elif competitor_count > 0:
        positive.append(f"+ established market ({int(competitor_count)} nearby)")
    if not positive:
        positive.append("+ baseline location potential")
    if not negative:
        negative.append("- limited local evidence")
    return score, positive[:3], negative[:3]


def land_recommendations(df_input: Any, feature_vector: Dict[str, Any] | None = None) -> list[dict[str, Any]]:
    results = []
    for business in BUSINESS_TYPES:
        score, positive, negative = score_business(business, df_input, feature_vector)
        results.append({"business": business.capitalize(), "score_percent": int(round(score)), "positive_factors": positive, "negative_factors": negative})
    return sorted(results, key=lambda item: item["score_percent"], reverse=True)
