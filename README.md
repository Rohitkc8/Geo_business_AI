# GeoBusiness AI

GeoBusiness AI is a geospatial decision-support prototype with two workflows:

- **LAND → BUSINESS**: analyse a selected location and rank supported business categories.
- **BUSINESS → LAND**: select a business category and search area to rank candidate geographic cells.

> **Important:** This system predicts location/business suitability based on observed geographic patterns and available data. It does not guarantee business profitability or success.

## 1. Project title

**GeoBusiness AI — Geographic business and location suitability prototype**

## 2. Problem statement

Choosing a business or location often relies on manual inspection of population, nearby businesses, amenities, transport and roads. These signals are scattered across sources and difficult to compare consistently across several locations.

## 3. Motivation

The project makes a small, inspectable prototype for bringing geographic context into an initial site-selection conversation. It shows the observations and model explanations alongside recommendations instead of presenting a score without context.

## 4. Existing approach

Typical approaches include local knowledge, manual map searches, broker advice, and spreadsheet comparisons. They can be useful, but are time-consuming, inconsistent between areas, and may not expose the assumptions behind a recommendation.

## 5. Proposed system

The backend geocodes a user query, collects nearby map and population data, derives spatial features, and sends them to one of two trained models. The React application presents land recommendations or a ranked, interactive candidate-cell heatmap. Candidate details expose the geographic values used for interpretation.

## 6. System architecture

```text
React + Leaflet UI
       │ HTTP/JSON
FastAPI API ──► Nominatim (geocoding)
       │
       ├──► Overpass / OpenStreetMap (POIs, shops, roads)
       ├──► WorldPop (population estimate)
       ├──► feature_engineer.py
       ├──► Model 1 / Model 2 + SHAP explanations
       └──► optional PostgreSQL/PostGIS persistence schema
```

Cached raw, processed, and population responses are stored under `backend/data/` to reduce repeated requests. PostgreSQL/PostGIS is defined for persistence but is not required for the current inference endpoints.

## 7. Data sources

- **OpenStreetMap via Overpass API**: amenities, shops, offices, roads and bus stops. Data quality depends on OSM coverage and tagging.
- **Nominatim**: text-query geocoding.
- **WorldPop 2020 API**: historical population estimates for the requested bounding area.
- **Local cache**: previously obtained source responses; it is not synthetic geographic data.

Respect the upstream providers’ terms, rate limits and licences. OSM data is attributed in the map/API metadata.

## 8. Data pipeline

1. The UI sends a location or area string to `POST /api/geocode`.
2. The API resolves coordinates with Nominatim.
3. `GeoDataService` loads an exact cache entry or queries Overpass and WorldPop.
4. `SpatialFeatureEngineer` counts features and derives density/distance measures.
5. The API runs Model 1 or Model 2 and SHAP-based explanations.
6. The response is rendered as recommendation cards or candidate grid cells.

For BUSINESS → LAND, the API centres a configurable grid on the search area, evaluates every available cell, skips cells with collection failures, and sorts successful cells by the raw Model 2 output.

## 9. Feature engineering

Available feature values include:

- population, population density, households and residential density;
- counts of schools, colleges, hospitals, clinics, bus stops, grocery shops, pharmacies, restaurants, cafes and banks;
- selected-category competitor count and total-business density;
- road density and distance to a major road.

Major-road distance is `-1` when no qualifying road is found within the search radius. Missing population inputs are handled as `0` for model-input construction; this is a limitation, not an assertion that population is zero.

## 10. Dataset 1 — land-to-business

`backend/data/training/land_business_dataset.csv` currently contains **4 rows**. Inputs are population, population density, residential density, road density and distance to major road. Targets are observed presence labels for restaurant, pharmacy, bank, grocery and clinic.

## 11. Dataset 2 — business-to-land

`backend/data/training/business_location_dataset.csv` currently contains **8 rows** and was generated for pharmacy expansion cells. It contains geographic context, amenity/transport/road features, and `target_demand_proxy_score`.

That target is a proxy calculated during data generation from population, selected-category competitor count and business density. It is not a measured revenue, profit, customer count, or business-success label.

## 12. Model 1 — Land → Business

Model 1 is a `RandomForestClassifier` trained as a multi-output classifier. Its five output labels are `has_restaurant`, `has_pharmacy`, `has_bank`, `has_grocery`, and `has_clinic`. The API returns predicted positive-class probabilities as percentage-style suitability values and exposes leading SHAP contributions.

## 13. Model 2 — Business → Land

Model 2 is a `GradientBoostingRegressor` that predicts `target_demand_proxy_score`. It uses school, college, hospital and bus-stop counts, road density, and distance to major road. Population, competitor count, business density, households and related derived variables are deliberately excluded from its training inputs to avoid direct target leakage. Its returned `model_score` is the raw regressor output; the UI only colours it relatively within the current grid.

## 14. Training methodology

Both training scripts use a fixed random train/test split and `StandardScaler` preprocessing. Model 1 uses a class-balanced Random Forest with 100 estimators; it also trains a `DummyClassifier` baseline. Model 2 uses a mean `DummyRegressor` baseline and a Gradient Boosting Regressor with 100 estimators, depth 3, and learning rate 0.1.

The scripts are `backend/train_model.py` and `backend/train_business_model.py`. Generate source datasets first with `generate_dataset.py` and `generate_business_dataset.py` if data collection is appropriate for your environment.

## 15. Evaluation

The training scripts print classification reports and multilabel confusion matrices for Model 1, and MAE, RMSE, R², Spearman rank correlation, train/test R², and feature importances for Model 2. No aggregate performance numbers are claimed here: the checked-in datasets are extremely small, and random splits of adjacent geographic cells can leak spatial similarity. Treat this as a prototype, not validated predictive performance.

## 16. API documentation

Start the backend and visit `http://127.0.0.1:8000/docs` for the generated OpenAPI interface.

| Endpoint | Purpose |
| --- | --- |
| `GET /` | Health response |
| `POST /api/geocode` | Resolve `{ "query": "RS Puram, Coimbatore" }` |
| `GET /api/business-types` | Supported selectable categories |
| `GET /api/location-details` | Geographic feature vector for `lat`, `lon`, `radius` |
| `GET /api/map-data` | Nearby features as GeoJSON |
| `POST /api/analyze-location` | Model 1; `{lat, lon, radius}` |
| `POST /api/find-best-locations` | Model 2; `{business_type, start_lat, start_lon, steps, step_size}` |

Radius is validated to 50–5000 metres. Grid steps are 1–10 and step size must be positive and no greater than 0.05 degrees. Blank business categories are rejected. Geographic-provider errors, no usable cells, and model failures return meaningful HTTP errors rather than fabricated output.

## 17. Database architecture

The optional SQLAlchemy/GeoAlchemy2 schema in `backend/db/models.py` defines `locations`, `businesses`, `roads`, `schools`, `colleges`, `hospitals`, `population_grids`, and `analysis_results`. Geometry columns use SRID 4326 and are intended for PostgreSQL/PostGIS spatial indexing.

Set `DATABASE_URL` in `backend/.env` before using it. Current API inference reads live/cached geographic sources and does **not** yet persist analysis results, so an unavailable database does not block the user workflows.

## 18. Frontend architecture

`frontend/src/App.tsx` contains the two workflow views. It uses React state for inputs, loading/error state, candidate selection and results. Leaflet/React-Leaflet renders basemap tiles, Model 1 map observations, and Model 2 clickable candidate rectangles. API calls are made to `http://127.0.0.1:8000/api` in development.

## 19. Installation

Prerequisites: Python 3.12+, Node.js, npm, and optionally PostgreSQL with PostGIS.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-test.txt

cd ..\frontend
npm install
```

For PostGIS, create the database, enable the PostGIS extension, and set `DATABASE_URL` in `backend/.env`. Do not commit real credentials.

## 20. Running instructions

In one terminal:

```powershell
cd backend
uvicorn main:app --reload --port 8000
```

In another terminal:

```powershell
cd frontend
npm run dev
```

Open the URL shown by Vite. For LAND → BUSINESS, search a location such as `RS Puram, Coimbatore`. For BUSINESS → LAND, choose `Pharmacy` and search `Coimbatore`.

### Testing

```powershell
cd backend
pytest -q

cd ..\frontend
npm run test
npm run build
npm run lint
```

Backend tests mock external providers and models where appropriate. Frontend tests mock Leaflet and API responses, covering both workflows and visible failure states.

## 21. Limitations

- Very small checked-in training datasets; results are not production validation.
- Model 2’s target is a geographic demand proxy, not commercial outcome data.
- OSM completeness, tags, WorldPop coverage, and geocoding results vary by place and date.
- Provider timeouts can leave some candidate cells unavailable.
- Road density may use a fallback feature count when network graph collection is unavailable.
- A local PostGIS database is optional and not yet used to persist inference output.
- Scores are decision-support signals, not financial, legal, safety, or investment advice.

## 22. Future improvements

- Collect larger, geographically diverse, time-stamped datasets with real outcome labels.
- Use spatially blocked cross-validation and publish evaluation results with uncertainty.
- Train business-type-specific Model 2 models and calibrate output interpretation.
- Add retry/backoff, provider health reporting, and asynchronous grid processing.
- Persist source provenance, feature snapshots and analysis results in PostGIS.
- Add authentication, rate limiting, cache expiry, observability and deployment configuration.
- Add accessible map controls, candidate exports, and user-provided constraints such as rent, zoning and budget.
# Geo_business_AI

## 23. Current product capabilities

The current application includes a polished decision workspace built around two analysis modes:

- **Evaluate Land (LAND → BUSINESS):** geocode a location, inspect nearby amenities and competitors, rank business opportunities, estimate land price per cent, and discover mapped empty-land parcels.
- **Place Business (BUSINESS → LAND):** select a business type, scan a centred geographic grid, rank candidate locations, and inspect each candidate’s score, population, competition, infrastructure signals, and individual land-budget estimate.
- **Per-location budget estimates:** every candidate returned by `POST /api/find-best-locations` now includes `budget_estimate`, containing the estimated price per cent, model source, population-density factor, road distance, school count and hospital count.
- **Budget-aware map visualization:** candidate cell fill represents relative business suitability, while the cell border represents relative budget from lower to higher. Map popups and the selected-location panel show the exact estimate.
- **Workspace UX:** saved analyses persist in browser storage, saved locations can be reopened or removed, profile preferences can be saved locally, and dark mode/map-label preferences are available.

### Budget interpretation

Budget figures are **prototype planning estimates per cent**, not final plot prices or total acquisition costs. The current model is trained on synthetic data using population density, road distance, school count and hospital count. Replace it with time-stamped local transaction data before using it for commercial valuation.

### Frontend interaction model

The React + Leaflet frontend provides accessible form labels, loading and error states, responsive layouts, category-specific map colors, competitor highlighting, clickable candidate cards, clickable map cells, and a collapsible legend for suitability and budget scales.
