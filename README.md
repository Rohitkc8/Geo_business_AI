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

The map also supports interactive **Center** and **Fit results** actions. Center returns to the searched area, while Fit results frames all candidate cells or available-land parcels so users can inspect the full analysis region without manually zooming.

### Recommended next milestones

1. Replace the synthetic budget model with time-stamped local land transactions and expose confidence ranges.
2. Add user constraints such as rent, plot size, zoning, parking, budget ceiling and target customer profile.
3. Persist analysis snapshots and source provenance in PostGIS so results can be audited and compared over time.
4. Add authentication, rate limiting, provider-health monitoring and background processing for larger candidate grids.
5. Add exports (CSV/PDF), side-by-side comparisons and an admin workflow for reviewing model quality.
## 24. Comparison and reporting

The BUSINESS → LAND workflow supports a shortlist of up to four candidate locations. Users can add candidates with **Compare**, inspect suitability, estimated budget per cent, population, competitors, schools and road distance side by side, clear the shortlist, and export the current analysis as a print-ready PDF report from the analysis header. The browser print dialog is used so the user can choose “Save as PDF” without a reporting server.

## 25. Real land-price data integration plan

The current budget model is a prototype estimate. To integrate real data safely, add a provider adapter rather than calling a vendor directly from the React app:

1. Create a backend `LandPriceProvider` interface with `get_price_estimate(lat, lon, radius, property_type)` and a normalized response containing `price_per_cent`, `currency`, `source`, `observed_at`, `sample_count`, `confidence_low`, `confidence_high`, and `provenance_url`.
2. Implement adapters for official registration/transaction datasets, government open-data portals, licensed market-data vendors, or a user-uploaded CSV. Keep provider credentials and API keys in backend environment variables.
3. Normalize units before storage: INR per square metre, cent and acre; retain the original unit and conversion method. Store time period, transaction type, land-use classification and whether the value is an asking price or a registered transaction.
4. Match transactions to coordinates using geocoding or parcel identifiers, then aggregate nearby observations using distance and recency weighting. Return a confidence range when there are too few comparable observations.
5. Cache provider responses with a timestamp, respect rate limits, log provenance, and expose a `data_quality` field so the UI can distinguish live market data from the fallback model.
6. Replace `budget_estimate` in the API only after validation against held-out local transactions; keep the synthetic model as a clearly labelled fallback for areas without coverage.

Recommended API shape:

```text
GET /api/land-price?lat=...&lon=...&radius=...&land_type=...
→ { price_per_cent, currency, confidence_low, confidence_high, source, observed_at, sample_count, data_quality }
```

The backend now implements this endpoint. It checks sources in this order:

1. `LAND_PRICE_PROVIDER_URL` — an optional JSON provider endpoint. It receives `lat`, `lon`, `radius` and `land_type` query parameters and must return `price_per_cent` (or `price`).
2. `LAND_PRICE_DATA_PATH` — an optional local CSV containing `lat`, `lon`, `price_per_cent` and an optional `land_type` column. Nearby rows are matched by radius and aggregated using the median price.
3. The existing budget model — returned as `data_quality: synthetic_fallback` so it is never confused with live market data.

Example local configuration:

```bash
export LAND_PRICE_DATA_PATH=/absolute/path/land_transactions.csv
export LAND_PRICE_PROVIDER_URL=https://your-provider.example/api/land-price
```

The clicked-parcel UI now calls `/api/land-price`, displays the source and data quality, and preserves the fallback behavior when no real provider or local transaction file is configured.

Do not expose provider keys in the frontend, scrape sources that prohibit automated access, or present asking prices as certified valuations.

## 26. Data freshness and prediction accuracy

The application combines different data types, and they should not be interpreted as equally current:

- **Map features and competitors:** fetched from OpenStreetMap through Overpass when an analysis runs, subject to OSM coverage, cache state, and Overpass rate limits.
- **Population:** WorldPop **2020**, a historical raster baseline; it is not a live census feed.
- **Suitability scores:** produced by the repository's trained prototype models using spatial features. These scores are decision-support rankings, not validated forecasts.
- **Land budgets:** prototype estimates unless `LAND_PRICE_PROVIDER_URL` or `LAND_PRICE_DATA_PATH` is configured with real transaction data.

The UI now shows a provenance strip for business-placement scans and keeps map colors light so candidate cells and competitor markers are easier to inspect. For production accuracy, the next priority is validating model outputs against recent local transactions and actual business openings/closures, then retraining with a time-based holdout and adding provider freshness/confidence fields to every result.
