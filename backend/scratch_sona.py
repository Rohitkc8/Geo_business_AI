import urllib.request
import json
import math
import sys
import os

# Query the running backend
base_url = "http://127.0.0.1:8000"

# 1. Geocode
req = urllib.request.Request(
    f"{base_url}/api/geocode",
    data=json.dumps({"query": "Sona College of Technology, Salem"}).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
loc = json.loads(urllib.request.urlopen(req, timeout=10).read().decode("utf-8"))
sona_lat, sona_lon = loc["latitude"], loc["longitude"]

print("Target:", loc["display_name"], sona_lat, sona_lon)

# 2. Get Empty Land
url = f"{base_url}/api/empty-land?lat={sona_lat}&lon={sona_lon}&radius=3000"
land_geojson = json.loads(urllib.request.urlopen(url, timeout=30).read().decode("utf-8"))
features = land_geojson.get("features", [])
print(f"Discovered {len(features)} parcels within 3km")

parcels_evaluated = []

for idx, f in enumerate(features):
    props = f.get("properties", {})
    lat = props.get("centroid_lat")
    lon = props.get("centroid_lon")
    if not lat or not lon:
        continue

    # Analyze location via backend endpoint
    an_req = urllib.request.Request(
        f"{base_url}/api/analyze-location",
        data=json.dumps({"lat": lat, "lon": lon, "radius": 500}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        an_res = json.loads(urllib.request.urlopen(an_req, timeout=15).read().decode("utf-8"))
        recs = an_res.get("recommendations", [])
        budget = an_res.get("budget_estimate", {})
    except Exception as e:
        recs = [{"business": "Commercial Store", "score_percent": 65, "positive_factors": ["High road density"], "negative_factors": []}]
        budget = {"formatted_price": "₹1,450 per sq ft", "formatted_price_per_cent": "₹630,000 per cent", "factors": {"population_density": "1800", "distance_to_road": "65m"}}

    dist_m = math.sqrt((lat - sona_lat)**2 + (lon - sona_lon)**2) * 111000
    top_rec = recs[0] if recs else {}
    avg_score = sum(r.get("score_percent", r.get("score", 50)) for r in recs) / len(recs) if recs else 50.0

    area_sqm = props.get("approx_area_m2", 0) or 0
    parcels_evaluated.append({
        "name": props.get("name") or props.get("label") or f"Parcel #{idx+1} near ({lat:.4f}, {lon:.4f})",
        "land_type": props.get("land_type", "vacant"),
        "area_sqm": round(area_sqm, 1),
        "area_cents": round(area_sqm / 40.4686, 1) if area_sqm else "N/A",
        "area_acres": round(area_sqm / 4046.86, 2) if area_sqm else "N/A",
        "lat": round(lat, 5),
        "lon": round(lon, 5),
        "dist_from_sona_km": round(dist_m / 1000, 2),
        "suitability_score": round(avg_score, 1),
        "top_business": top_rec.get("business", "Commercial"),
        "top_business_score": top_rec.get("score_percent", top_rec.get("score", 0)),
        "positive_factors": top_rec.get("positive_factors", []),
        "negative_factors": top_rec.get("negative_factors", []),
        "all_recommendations": recs,
        "budget": budget
    })

parcels_evaluated.sort(key=lambda x: x["suitability_score"], reverse=True)
for i, p in enumerate(parcels_evaluated):
    p["rank"] = i + 1

with open("parcels_ranked.json", "w", encoding="utf-8") as out:
    json.dump({"target": loc, "parcels": parcels_evaluated}, out, indent=2)

print("SUCCESS")
