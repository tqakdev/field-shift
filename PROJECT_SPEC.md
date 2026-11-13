# PROJECT_SPEC.md — "Field Shift" (NASA Space Apps Challenge 2026)

> You are a senior full-stack engineer and geospatial data scientist. Build the complete, production-quality
> project described below, **phase by phase**. After each phase: run the app and the tests, fix every error,
> then stop and give me a short report (what works, what's left, any decisions you made). Do not start the
> next phase until I say "continue".

---

## 0. Context (read first)

**Hackathon:** NASA Space Apps Challenge 2026, held Nov 14–15, 2026 (about 48 hours).
**Challenge:** "Field Shift: Adapting Farms with NASA Data".
**Judging criteria (equal weight):** Impact, Creativity, Validity, Relevance, Presentation.

**What the challenge asks for:** a decision-support tool that combines NASA Earth observations with local soil
information, crop characteristics and farmer priorities. It helps farmers explore crop-rotation strategies that
improve soil health and resilience to changing temperature, rainfall and water conditions. From the brief:

- Compare **at least 3 rotation strategies, including the farmer's existing rotation**.
- For each strategy, explain: **why it was suggested, what evidence supports it, what benefits it may offer,
  where information gaps exist, and any risks that need local review** by farmers or agricultural experts.
- Point out **times when fields are usually bare**, **seasons when current crops look more vulnerable**, and
  opportunities to break pest cycles, reduce water demand, improve infiltration, or add income.
- Explain scientific terms (evapotranspiration, soil-moisture anomaly, NDVI, frost risk, water balance).
- Explain how satellite data differs from ground measurements.
- Combine (harmonize) datasets with different spatial and temporal resolutions onto a common analysis grid
  and time step.
- Use an "SI" approach. In 2026, US federal agencies, including NASA, say "SI" (Super Intelligence) where
  others say "AI". Find seasonal patterns and stress periods, and **show uncertainty**.
- Maps, timelines, overlays, and scenario sliders (e.g. adjust rainfall or temperature).
- Farmer-centered design for non-technical users. Let farmers enter priorities and constraints (water
  availability, equipment, markets).
- Remind users throughout that the tool **supports, not replaces,** local expertise. Mark where human
  judgment matters most.

**Positioning:** "Works anywhere on Earth using NASA satellite data, with extra precision in the US."
- **Global core (§4):** works for any field. The farmer enters the current rotation and soil type.
- **US enhancement module (§4b, Phase 7):** when the field is in the contiguous US, the app auto-detects the
  rotation (Cropland Data Layer), auto-fills soil properties (SSURGO), adds real prices and county yields (USDA
  NASS / AMS), and validates satellite rain against volunteer rain gauges (CoCoRaHS). The farmer can always
  override auto-filled values.

---

## 1. Definition of done

A judge opens the deployed URL and can, in under 30 seconds:
1. Pick a pre-loaded demo field, or draw a new field anywhere on the map.
2. See the field's conditions: a 12-month seasonal profile (NDVI, soil moisture, rain, temperature, water
   balance), bare-soil months, stress months, frost window, and a satellite time-lapse of the field.
3. Enter the current rotation, soil type, water access, and priority weights (sliders).
4. See **3 or more strategy cards** (current rotation + at least 2 alternatives), each with scores, why,
   evidence (real numbers, each tagged with its dataset), benefits, data gaps, risks for local review,
   and a confidence level.
5. Move a "what-if" slider (rainfall −30%…+30%, temperature +0…+3 °C) and watch the scores update.
6. Open a glossary and a "How it works / data sources" page.

Demo fields must load instantly from a cache. The app must **run fully in demo mode without any Earth Engine
credentials**. Live analysis of new fields needs credentials.

---

## 2. Tech stack (use exactly this unless something is broken; then tell me)

**App (UI)**
- Python 3.11+, **Streamlit** multipage app (no React, no FastAPI for the product)
- Map: `folium` + `streamlit-folium` + `folium.plugins.Draw` for polygon drawing; Esri World Imagery
  basemap (OSM as a documented fallback if imagery tiles fail)
- Charts: **Plotly** (`st.plotly_chart`)
- Timelapse: `st.image` on a cached static GIF (demo fields); live fields may show a fresh EE URL / GIF
- State: `st.session_state` for selected field + farmer inputs; `@st.cache_data` (with TTL) on every Earth
  Engine / POWER / demo-cache load. What-if and priority sliders **only** re-run pure-Python scoring
  (milliseconds), never data extraction. If the installed Streamlit version supports `st.fragment`, use it
  for the strategy / what-if section; **verify** `hasattr(st, "fragment")` (or docs for that version)
  before using — otherwise render the section normally.

**Core package (plain Python, imported by Streamlit)**
- Pydantic v2 models as **internal data contracts** (same shapes as the former API payloads)
- `earthengine-api` (service account), `httpx` (NASA POWER), `pandas`, `numpy`, `scikit-learn`
- File-based JSON (+ GIF) cache under `fieldshift/cache/` (committed demo artefacts)
- `pytest` for tests, `ruff` for linting
- `pydantic-settings` / env for credentials (`EE_*`, optional US keys)

**Ops**
- `requirements.txt` (pinned) + `pyproject.toml` (ruff / pytest config)
- `Dockerfile` / optional `docker-compose.yml` running Streamlit on one port
- Deploy: Streamlit Community Cloud and/or Render (single Streamlit service). No separate Vercel frontend.
- `.env.example` documenting every environment variable; Streamlit Cloud may use Secrets instead of `.env`

---

## 3. Repository structure

```
field-shift/
├── PROJECT_SPEC.md
├── README.md                    # pitch, screenshots, NASA data used, setup, demo script
├── AI_USAGE.md
├── docker-compose.yml           # optional: single Streamlit service
├── Dockerfile
├── .env.example
├── requirements.txt
├── pyproject.toml
├── app.py                       # Streamlit entry + st.navigation routes
├── views/
│   ├── home.py                  # demo picker + analyze-my-field map
│   ├── field.py                 # conditions, timelapse, inputs, priorities, strategies, what-if
│   └── how_it_works.py          # sources, scoring, SI, limitations, glossary
├── ui/                          # thin Streamlit helpers (map, charts, cards) — no business logic
│   ├── map.py
│   ├── charts.py
│   ├── strategy_cards.py
│   └── mock_banner.py
├── fieldshift/                  # plain Python package (Streamlit imports this; no HTTP layer)
│   ├── __init__.py
│   ├── config.py                # env settings (pydantic-settings)
│   ├── models.py                # Pydantic schemas / data contracts (see §7)
│   ├── cache.py                 # read/write demo JSON + GIF paths
│   ├── data/
│   │   ├── ee_client.py         # EE init (service account), helpers
│   │   ├── extract_ee.py        # per-field monthly feature extraction
│   │   ├── extract_power.py     # NASA POWER daily → monthly + frost/heat/GDD
│   │   ├── harmonize.py         # common monthly time step + field-level aggregation
│   │   ├── timelapse.py         # EE video/GIF; demo = static file in cache/
│   │   ├── cross_checks.py      # VIIRS/MODIS, GLDAS/SMAP/ERA5 agreement (Phase 7)
│   │   ├── gaez.py              # GAEZ raster download + point sampling (Phase 7)
│   │   └── us/                  # US module (Phase 7)
│   │       ├── cdl.py, ssurgo.py, nass.py, ams.py, cocorahs.py, geocode.py
│   ├── engine/
│   │   ├── crops.json           # crop knowledge base (see §5)
│   │   ├── features.py
│   │   ├── anomalies.py
│   │   ├── candidates.py
│   │   ├── scoring.py
│   │   ├── scenarios.py
│   │   └── explain.py
│   └── cache/                   # committed demo_*.json + demo_*_timelapse.gif
├── scripts/
│   └── precompute_demo.py       # builds fieldshift/cache/demo_* for demo fields
├── tests/
└── mock/                        # labelled MOCK JSON for scaffold / no-credential UI only
```

> **Note:** The Phase 1 React + FastAPI tree under `frontend/` and `backend/` is superseded by this layout.
> Migrate useful pieces (Pydantic models, mock JSON shapes) into `fieldshift/` and `mock/`, then remove the
> unused React/FastAPI app code once the Streamlit scaffold runs.

---

## 4. Data sources (global only)

**Rules:**
- Before writing any code that uses a dataset, check its ID, band names and date range: print
  `ee.ImageCollection(id).first().bandNames()` and the min/max dates. Earth Engine copies can lag behind the
  original archive, so compute the analysis end date dynamically from the data that actually exists.
- **Never invent data values.** If a dataset has no data for a field or period, mark it as a data gap and lower
  the confidence. Mock JSON lives in repo-root `mock/` and must be shown with a visible **MOCK DATA** banner.
- Tag every number shown to the user with its source dataset via a `ui/` helper that renders a
  `source: <dataset>` caption (not a React component).

| Purpose | Dataset | Earth Engine ID / access | Notes |
|---|---|---|---|
| NDVI, bare soil, crop vigor (field scale) | Sentinel-2 SR (ESA) | `COPERNICUS/S2_SR_HARMONIZED` + cloud mask with `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` (cs ≥ 0.6) | 10 m, 2017→ |
| NDVI, longer history | Landsat 8/9 C2 L2 | `LANDSAT/LC08/C02/T1_L2`, `LANDSAT/LC09/C02/T1_L2` | 30 m. Apply scale factors and the QA_PIXEL cloud mask |
| Long NDVI baseline for anomalies | MODIS Terra VI | `MODIS/061/MOD13Q1` | 250 m, 16-day, 2000→ |
| Soil moisture (surface + root zone) | SMAP L4 | `NASA/SMAP/SPL4SMGP/008` | 3-hourly, ~11 km. Use `sm_surface`, `sm_rootzone` |
| Precipitation | GPM IMERG V07 monthly | `NASA/GPM_L3/IMERG_MONTHLY_V07` | Band `precipitation` is in mm/hr; convert to mm/month |
| Evaporation, potential ET, soil water, temperature | ERA5-Land monthly | `ECMWF/ERA5_LAND/MONTHLY_AGGR` | Flow bands end in `_sum` (e.g. `total_precipitation_sum`, `total_evaporation_sum`, `potential_evaporation_sum`). Check signs and units (m) |
| Elevation and slope | SRTM | `USGS/SRTMGL1_003` | 30 m. Slope from `ee.Terrain.slope` |
| Regional water storage trend | GRACE/GRACE-FO JPL Mascon (CRI) | `NASA/GRACE/MASS_GRIDS_V04/MASCON_CRI` | Very coarse (3° mascons). Context only; never present as field-level |
| Daily weather (frost, heat, GDD) | NASA POWER | `GET https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,ALLSKY_SFC_SW_DWN&community=AG&latitude={lat}&longitude={lon}&start=YYYYMMDD&end=YYYYMMDD&format=JSON` | No API key. ~0.5° grid. Fill value −999 → NaN |
| Heat stress / ET hotspots (stretch goal) | ECOSTRESS | NASA AppEEARS API (only if time allows) | Coverage only ~52°N–52°S, irregular revisits. Optional; mark as a data gap if missing |
| NDVI continuity / cross-check for MODIS | VIIRS VI (NASA) | `NASA/VIIRS/002/VNP13A1` | 500 m, 16-day, 2012→. Band `NDVI` (check the scale factor). Use where MODIS has gaps, and report MODIS-vs-VIIRS agreement as a validity metric |
| Second (NASA) soil-moisture and ET source | GLDAS-2.1 Noah | `NASA/GLDAS/V021/NOAH/G025/T3H` | 3-hourly, ~28 km, 2000→. Bands `SoilMoi0_10cm_inst` (kg/m²), `Evap_tavg` (kg/m²/s → mm/month). Aggregate to monthly. Cross-check against SMAP/ERA5-Land; disagreement lowers confidence |
| Crop climate/soil suitability | FAO GAEZ v4 | GeoTIFF rasters from the GAEZ v4 Data Portal (FAO-hosted S3; get exact URLs from the portal's Data Access page) | ~9 km, global. Use the **suitability index** for each candidate crop (rain-fed and irrigated, high input). Download once for the ~15 crops, cache under `backend/data_static/gaez/`, and sample at the field centroid with `rasterio`. If a raster is unavailable, skip it and record a data gap |
| Surrounding vegetation structure (context only) | GEDI L4A/L4B biomass | Earth Engine catalog: search "GEDI L4" and use the gridded product if present | Only describes nearby tall vegetation (windbreaks, woodland). **Never** use it to score crops. Show it as one line of context, or leave it out if time is short |

### 4b. US enhancement module (Phase 7; only runs when the field centroid is in the contiguous US)

Detect "in CONUS" with a simple bounding polygon (or by checking that CDL has valid pixels for the field). Every US
feature must **degrade gracefully**: if an API key is missing or a call fails, the global core still works and
the UI shows "US data unavailable".

| Purpose | Dataset | Access | How to use it |
|---|---|---|---|
| **Auto-detect current rotation** | USDA NASS Cropland Data Layer | Earth Engine `USDA/NASS/CDL`, band `cropland` (30 m, annual) | For each of the last 8 years, take the **mode** class within the field polygon plus its share of the field. Map CDL class codes → `crop_id` through `cdl_codes` in `crops.json` (remember double-crop classes, e.g. 26 = winter wheat/soybeans). Infer the repeating rotation pattern (e.g. corn/soy alternating). Pre-fill the rotation input with a badge: "Detected from USDA Cropland Data Layer 2017–2024 (confidence X%)". The farmer can edit it |
| **Auto-fill soil** | USDA NRCS SSURGO (via Soil Data Access) | `POST https://sdmdataaccess.sc.egov.usda.gov/tabular/post.rest` with form/JSON body `{query: <T-SQL>, format: "JSON+COLUMNNAME"}`. Get map units for the polygon with `SDA_Get_Mukey_from_intersection_with_WktWgs84('<WKT>')` | Pull the dominant component and its surface horizon: texture class, organic matter (`om_r`), available water capacity (`awc_r`), drainage class, hydrologic soil group, erodibility (`kwfact`). Area-weight across map units. Pre-fill soil type and feed AWC/OM/kwfact into the water, soil-health and erosion scores. Use parameterized query building, and never interpolate unescaped user input into SQL |
| **Prices** | USDA NASS QuickStats (primary) | `GET https://quickstats.nass.usda.gov/api/api_GET/?key=$NASS_API_KEY&commodity_desc=CORN&statisticcat_desc=PRICE%20RECEIVED&agg_level_desc=STATE&state_alpha=IA&year__GE=2019&format=JSON` (free key) | State-level annual price received for each candidate cash crop → relative income tier (replaces the static `market_tier` for US fields). Check parameter values with `get_param_values` first. Max 50,000 records per request |
| **County yields** | USDA NASS QuickStats | Same API, `statisticcat_desc=YIELD`, `agg_level_desc=COUNTY`, with the county found by reverse-geocoding the centroid to a county FIPS code (e.g. FCC Area API or the Census geocoder; check availability) | 10-year county yield trend and variability for each crop → part of the income/climate-fit evidence ("Soybean yields in Story County varied ±9% over 10 years") |
| **Market news (bonus)** | USDA AMS MyMarketNews (MARS API) | `https://marsapi.ams.usda.gov/services/v1.2/reports`. Free personal key passed as the HTTP Basic auth username with an empty password (`$AMS_API_KEY`) | Optional: list reports, pick the grain/hay report(s) relevant to the field's state, and show a "recent local market" line on the income evidence. Skip it if time is short; QuickStats prices are enough |
| **Rain validation** | CoCoRaHS volunteer gauges (included in NOAA GHCN-Daily) | Find gauges within ~25 km and their daily precipitation through a public station-data API (e.g. RCC-ACIS `StnMeta`/`MultiStnData`, or NOAA NCEI daily-summaries). **Check the endpoint and parameters before coding** | Compare monthly gauge totals with IMERG for the field cell: report correlation, bias (%) and the number of gauges/months. Show it on a "How accurate is the satellite rain here?" panel. This is the strongest Validity evidence in the demo |

All US values carry a `source` tag and appear in the evidence lists, so judges see exactly where each number comes from.

**Analysis window:** 10 most recent complete years for optical/climate data. Use the full available record for
MODIS and POWER baselines.

**Harmonization (`harmonize.py`):** reduce every dataset to **field-level monthly values** (mean over the field
polygon, `ee.Reducer.mean()` / `median()` at the dataset's native scale, `bestEffort=True`,
`maxPixels=1e9`). Output one tidy table with columns `month (YYYY-MM), variable, value, unit, source, n_obs`.
Also build a **monthly climatology** (mean and standard deviation for each calendar month) for each variable.
Document why: datasets range from 10 m to ~55 km, so the common unit is the "field × month".

---

## 5. Crop knowledge base (`engine/crops.json`)

About 15 crops: maize/corn, soybean, winter wheat, spring wheat, barley, oats, sorghum, millet, alfalfa,
red clover, field pea, lentil/chickpea, canola/rapeseed, sunflower, cereal rye (cover), hairy vetch (cover),
radish (cover), cotton, rice.

Schema for each crop:
```json
{
  "id": "cereal_rye_cover",
  "name": "Cereal rye (cover crop)",
  "type": "cover|cash|forage",
  "family": "poaceae",
  "season": "cool|warm",
  "growing_days": [180, 240],
  "min_frost_free_days": 0,
  "gdd_base_c": 4,
  "gdd_required": 1000,
  "water_need_mm": [250, 400],
  "drought_tolerance": 0.8,
  "heat_tolerance": 0.3,
  "frost_tolerance": 0.95,
  "waterlogging_tolerance": 0.5,
  "nitrogen_fixing": false,
  "root_depth": "deep",
  "ground_cover": 0.9,
  "residue_organic_matter": 0.8,
  "erosion_protection": 0.9,
  "forage_value": 0.6,
  "market_tier": "none|low|medium|high",
  "pest_break_families": ["fabaceae", "brassicaceae"],
  "notes": "...",
  "sources": ["FAO ECOCROP", "USDA SARE Managing Cover Crops Profitably"],
  "needs_expert_review": true,
  "cdl_codes": [27],
  "gaez_code": "rye",
  "nass_commodity": null
}
```
`cdl_codes` = USDA Cropland Data Layer class values for this crop (check them against the CDL class table in the
Earth Engine catalog). `gaez_code` = the GAEZ v4 crop code used in raster file names (check it against the GAEZ
crop list, or set it to `null`). `nass_commodity` = the QuickStats `commodity_desc` value (e.g. "CORN", "SOYBEANS"),
or `null` for cover crops.
**Rules:** use typical, conservative published ranges. Fill `sources` honestly with the general reference
(FAO ECOCROP, FAO crop water-requirement guidance, SARE, university extension guides). If unsure of a
value, use a middle value and set `needs_expert_review: true`. Show the "values need local expert review" note
in the UI.

---

## 6. Rotation engine

### 6.1 Field features (`features.py`)
Compute from the harmonized table and POWER daily data:
- `bare_months`: calendar months where median NDVI < 0.2 in ≥ 60% of years. Report the frequency, e.g. "Nov–Mar
  bare in 8 of 10 years".
- `stress_months`: months where NDVI z-score < −1 together with a soil-moisture z-score < −1 **or**
  T2M_MAX > 35 °C on ≥ 5 days. Report how many years this happened.
- `frost_window`: average last spring frost and first autumn frost (T2M_MIN ≤ 0 °C), plus frost-free days.
- `gdd_annual` (base 10 °C), `heat_days` (T2M_MAX > 35 °C) per year, and the trend over the window.
- `rain_annual_mm`, `rain_cv` (year-to-year variability), `extreme_rain_months` (top 5% monthly totals).
- `water_balance_monthly` = precipitation − potential ET (ERA5-Land), plus the annual deficit.
- `slope_pct_mean` and `erosion_risk` = f(slope, extreme rain frequency, bare months) on a 0–1 scale.
- `soil_moisture_trend`, `grace_trend_cm_per_yr` (regional context only).
- `data_coverage`: per-variable count of valid months and gaps. This feeds into confidence.
- `cross_checks`: agreement between independent sources, i.e. MODIS vs VIIRS NDVI (correlation), SMAP vs GLDAS
  vs ERA5-Land soil moisture (anomaly correlation), and, for US fields, IMERG vs CoCoRaHS. Low agreement lowers
  confidence and is listed as a data gap.
- `gaez_suitability`: per candidate crop, suitability index (rain-fed and irrigated) at the field. Used in
  `climate_fit`.
- **US only:** `detected_rotation`, `soil` (SSURGO values), `prices`, `county_yields`, `rain_validation`.

### 6.2 Candidate strategies (`candidates.py`)
Always include:
1. **Current rotation** (from farmer input, e.g. maize → soybean).
2. **Current + cover crop** in the detected bare window. Choose the cover crop with the best frost/season fit.
3. **Legume/nitrogen swap:** replace one cash crop with a legume that fits the climate.
4. **Water-wise swap:** if the water deficit is high or rain variability is high, swap in a drought-tolerant
   crop (sorghum, millet, …).
5. Optional **diversified 3-year rotation**, e.g. maize → soybean → small grain + cover.

Filter out crops that fail climate fit: frost-free days < crop requirement, GDD < requirement, or water need >
(rain + irrigation allowance) by more than 30% when the farmer has no irrigation. Return the top 3–4
strategies plus the current rotation.

### 6.3 Scoring (`scoring.py`)
Each criterion is scored from 0 to 1. The formulas must be documented in code docstrings and on the About page:
- `water`: 1 − normalized(seasonal water need − effective rain); adjusted for the farmer's water access.
- `soil_health`: weighted mean of nitrogen fixing, residue/organic matter, root depth, and months covered
  (fewer bare months scores higher).
- `erosion`: ground cover during `extreme_rain_months` and bare months × slope factor.
- `pest_break`: number of distinct plant families in the rotation and whether consecutive crops share a family.
- `climate_fit`: margin on frost-free days, GDD, heat tolerance vs. heat days, drought tolerance vs. rain_cv,
  blended with the FAO GAEZ suitability index when available (e.g. 70% own margins / 30% GAEZ, documented).
- `income`: market tier mapping (none 0, low 0.3, medium 0.6, high 0.9) + a forage bonus if the farmer has
  livestock. **US fields:** replace the tier with normalized NASS price × county yield trend, penalized by
  yield variability.
- `soil_health` / `water` / `erosion` on **US fields** also use SSURGO organic matter, available water capacity
  and erodibility (`kwfact`) instead of the farmer's coarse soil class.
- `total` = Σ(weight × score) / Σweights, with weights from the priority sliders (defaults all equal).
- `confidence`: high, medium or low from `data_coverage`, `needs_expert_review` flags, and how close the
  scores are to each other.

### 6.4 "SI" component (`anomalies.py`)
- Build a feature vector per field-month: NDVI anomaly, soil-moisture anomaly, rain anomaly, water balance
  anomaly, heat days.
- Fit `sklearn.ensemble.IsolationForest` (random_state fixed) on all months of that field. Flag anomalous
  months, then summarise them by calendar month into "vulnerable seasons".
- Return an anomaly score and the main contributing variables for each flagged month, so the user sees why
  it was flagged.
- Show uncertainty: model contamination parameter, number of years used, and a plain sentence saying the
  model finds unusual patterns, not causes.
- Optional (behind env flag `LLM_EXPLAIN=false` by default): an LLM can rephrase card text. It may only reword
  facts from the JSON, never add new claims. The app must work fully without it.

### 6.5 What-if scenarios (`scenarios.py`)
Rain multiplier (0.7–1.3) and temperature offset (+0 to +3 °C). These change effective rain, the water
deficit, heat days and the frost window. Re-score the strategies and show how much each score changed.

### 6.6 Explanations (`explain.py`)
Template-based, deterministic text built from computed facts. Every card has:
- `why` (1–2 sentences referring to the field features)
- `evidence[]`: strings with numbers and a `source`, e.g.
  `{"text": "Field bare Nov–Mar in 8 of 10 years", "source": "Sentinel-2 NDVI"}`
- `benefits[]`, `data_gaps[]`, `risks_for_local_review[]` (always non-empty, e.g. "check local seed
  availability and herbicide carryover")

---

## 7. Package interface (no HTTP API; Pydantic models in `fieldshift/models.py`)

Streamlit calls the `fieldshift` package directly. There is **no FastAPI layer** for the product. The
functions below are the public surface; return types are Pydantic models (serialize with `.model_dump()`
only when writing cache JSON).

| Function | Returns | Notes |
|---|---|---|
| `list_demo_fields()` | `list[DemoField]` | `{id, name, country, polygon, climate_label}` |
| `load_demo_conditions(field_id)` | `FieldConditions` | From committed `fieldshift/cache/demo_{id}.json` |
| `analyze_field(polygon, name?)` | `FieldConditions` | Cache by polygon hash if present; else live EE + POWER. Raises a clear error (caught in UI) if no EE credentials |
| `get_timelapse(field_id, index="ndvi"|"rgb")` | path or URL metadata | **Demo:** static GIF under `fieldshift/cache/` (no EE URL expiry). **Live:** fresh EE URL / render per call; never reuse a live EE URL older than 1 hour |
| `list_crops()` | `list[CropSummary]` | Dropdown catalogue |
| `list_sources()` | `list[DataSourceMeta]` | How-it-works datasets table |
| `generate_strategies(field_id_or_conditions, StrategyRequest)` | `StrategyResult` | Pure scoring over already-loaded features + farmer inputs + scenario; **must not** call EE/POWER |
| `get_us_module(field_id)` | `UsModuleResponse` | Until Phase 7: null parts + reason in `errors[]` |
| `get_validation(field_id)` | `ValidationResponse` | Until Phase 7: `cross_checks=null` + reason in `errors[]` |

`StrategyRequest` / `StrategyCard` / `FieldConditions` keep the same fields as before. `StrategyCard`:
```json
{
  "id": "current_plus_cover",
  "name": "Maize → Soybean + Cereal rye cover",
  "sequence": [{"crop_id": "maize", "months": "May–Oct"}, {"crop_id": "cereal_rye_cover", "months": "Oct–Apr"}],
  "scores": {"water": 0.7, "soil_health": 0.85, "erosion": 0.9, "pest_break": 0.6, "climate_fit": 0.8, "income": 0.6, "total": 0.76},
  "delta_vs_current": {"total": 0.12},
  "why": "...",
  "evidence": [{"text": "...", "source": "Sentinel-2 NDVI"}],
  "benefits": ["..."],
  "data_gaps": ["..."],
  "risks_for_local_review": ["..."],
  "confidence": "high|medium|low"
}
```

Validation: polygon area 1–5000 ha, valid lat/lon. EE and POWER calls use ~60 s timeouts with clear
user-facing Streamlit messages (no JSON `{"detail":...}` HTTP errors).

**Performance contract:** `@st.cache_data(ttl=...)` wraps demo loads and live extract/harmonize. Slider
changes update `st.session_state` and call only `generate_strategies` / scenario helpers.

---

## 8. Streamlit UX (farmer-first, mobile-friendly, accessible)

Multipage Streamlit app:

Navigation (`st.navigation` in `app.py`): `/` Home · `/field` · `/how-it-works`.

1. **`views/home.py`:** hero line, "Try a demo field" cards/buttons (write `field_id` into
   `st.session_state` and `st.switch_page("views/field.py")`), "Analyze my field" with a Folium map +
   Draw plugin. Short "This tool supports, not replaces, your judgment" banner. In demo mode without EE
   credentials, disable live analyze and show "Live analysis unavailable".
2. **`views/field.py`**, one scrolling page:
   - **Your field:** Folium map with the polygon + timelapse via `st.image` on the cached GIF (or placeholder
     until precompute).
   - **Conditions:** Plotly 12-month chart (NDVI, soil moisture, rain, water balance) with shaded bare /
     stress months and frost window. Key-fact chips (frost-free days, heat days trend, rain variability,
     slope), each with a source caption / tooltip.
   - **About your farm:** current rotation (selectboxes), soil type (sand/loam/clay/silt + "don't know"),
     water access, livestock yes/no, priority sliders. **US fields (Phase 7):** pre-fill rotation/soil with
     an "Auto-detected from USDA CDL / SSURGO" badge and an edit path — do **not** render the badge until
     real data exists.
   - **How reliable is this data? (Phase 7):** Validation panel (e.g. IMERG vs CoCoRaHS, MODIS vs VIIRS).
     Do **not** show "coming soon" placeholders; omit the section until `cross_checks` exist.
   - **Options / strategy cards:** `st.columns` (3–4 cards side by side; stacked on narrow screens),
     `st.metric` for the total score with delta vs the current rotation, a small Plotly bar of the criterion
     scores, `st.expander` sections for Evidence / Benefits / Data gaps / Risks for local review, a colored
     confidence badge (high/medium/low), and a small `source: <dataset>` caption under every number. The
     current rotation card is visually marked as the baseline. What-if and priority sliders re-score live
     (scoring only — never re-extract). Prefer `st.fragment` for this block when available.
3. **`views/how_it_works.py`:** pipeline overview, datasets table from `list_sources()`, scoring
   formulas, SI model explanation, satellite vs ground data, limitations (incl. cut list), credits,
   glossary (NDVI, ET, soil-moisture anomaly, water balance, frost-free days, GDD, cover crop, N fixation).

**Mock / scaffold:** any UI path using `mock/` JSON must show a visible **MOCK DATA** banner; mock numbers
must be obviously round placeholders.

Design: clean, earthy palette via Streamlit theme / light custom CSS if needed; large readable type; no
jargon without a help tooltip. Live analysis spinner: "Analyzing 10 years of NASA data… (~30–60 s)".

---

## 9. Demo fields (`scripts/precompute_demo.py`)

Pre-compute and commit JSON for 3 contrasting fields. Draw a ~50–100 ha polygon on cropland near each point and
check visually on the satellite basemap that it is actually farmland. Adjust the coordinates if not:
- **Iowa, USA** (humid, maize–soybean), around 42.0° N, 93.6° W
- **Western Kansas, USA** (semi-arid, wheat), around 38.4° N, 99.3° W
- **Punjab, India** (irrigated rice–wheat, heat stress), around 30.9° N, 75.8° E

The script runs extraction → features → anomalies → default strategies, then writes
`fieldshift/cache/demo_{id}.json`. Timelapse GIFs are **downloaded during precompute** and stored as static
files in `fieldshift/cache/` (e.g. `demo_{id}_timelapse.gif`). Demo fields never rely on expiring EE URLs.
Live fields may request a fresh EE URL (TTL ≤ 1 hour) when credentials are present.

---

## 10. Earth Engine auth and config

- Service account JSON is passed via env (or Streamlit Secrets with the same keys):
  `EE_SERVICE_ACCOUNT`, `EE_PRIVATE_KEY_JSON` (contents or path), `EE_PROJECT`.
- If they are missing, the Streamlit app starts in **demo mode** (cached fields only) and the Home page
  shows "Live analysis unavailable" on the Analyze control.
- US module keys (both optional; free registration): `NASS_API_KEY` (QuickStats), `AMS_API_KEY`
  (MyMarketNews). If a key is missing, skip that feature and record a reason in `errors[]`. Never block the app.
- Demo caches must include the US-module results for the Iowa and Kansas fields, so the demo needs no keys.
- Never commit secrets. Add `.gitignore` entries for `.env`, service-account JSON, and local secret files.
- Local: copy `.env.example` → `.env`. Streamlit Community Cloud: set the same keys under App settings →
  Secrets (TOML). The `fieldshift.config` loader should accept either env vars or `st.secrets` when running
  under Streamlit.

---

## 11. Quality bar

- Type hints everywhere. Docstrings on public functions (params, returns, units).
- `pytest` tests: feature derivation on a synthetic series, scoring monotonicity (more cover gives a better
  erosion score), candidate filtering, scenario re-scoring, POWER −999 handling, credential loading,
  package interface functions, and a **smoke test that imports every Streamlit page** without errors.
- `ruff` clean. No TypeScript / npm frontend build step.
- No dead code, no TODOs left in demo-critical paths.
- README: problem, solution, screenshots/GIF, **NASA and partner data used (list with links)**, architecture,
  how SI is used, limitations, local setup (with and without EE credentials), Streamlit Community Cloud
  deployment, a 2-minute demo script, and team credits.

---

## 12. Phases (stop after each one and report)

1. **Streamlit scaffold:** new repo layout (`app.py`, `views/`, `fieldshift/`, `ui/`, `mock/`), Pydantic models
   migrated into `fieldshift/models.py`, `.env.example`, `requirements.txt` / `pyproject.toml`, Dockerfile,
   lint/test commands. Multipage UI runs on **labelled MOCK** data. React (`frontend/`) and FastAPI
   (`backend/`) trees are removed.
2. **Data layer:** `ee_client`, `extract_ee`, `extract_power`, `harmonize`, `timelapse`. Verify dataset IDs and
   bands (print them). A CLI `python -m fieldshift.data.extract_ee --lat .. --lon ..` prints the monthly table
   for one field.
3. **Engine:** `crops.json`, features, anomalies, candidates, scoring, scenarios, explain, all with unit tests.
4. **Wire package + demos:** Streamlit calls `fieldshift` for demo fields; run `scripts/precompute_demo.py`
   (or document the credentialed command for me); commit `fieldshift/cache/demo_*.json` (+ static GIF
   timelapses). `@st.cache_data` on loads; graceful empty US/validation until Phase 7.
5. **Full Field UX:** replace mocks with real package results. Complete §8 (conditions Plotly chart, Folium
   map, farmer inputs, priorities, strategy cards, what-if re-score without re-extracting, How-it-works page,
   glossary). Verify `st.fragment` before using it for strategies/what-if.
6. **Polish and ship:** error/loading states, theme/accessibility pass, README, deploy Streamlit (Community
   Cloud and/or Render), end-to-end check of the Definition of Done in §1. List anything I must do manually
   (EE service account, deploy secrets). **Demo-ready at end of this phase. Phase 7 is extra.**
7. **Extended data coverage** (only after Phase 6 is shipped and deployed). Do these in order, and commit and
   redeploy after each one so a half-finished step never breaks the demo:
   1. Global extras: VIIRS + GLDAS cross-checks, validation panel in Streamlit.
   2. US module: CDL rotation auto-detect → SSURGO soil auto-fill → NASS prices/yields → CoCoRaHS rain validation.
   3. FAO GAEZ suitability in `climate_fit`.
   4. Optional: AMS market line, GEDI context line.
   Re-run `precompute_demo.py` so the demo caches include everything. Update the README datasets list.

**General rules:** do not invent libraries, dataset IDs or band names. Check them, and if something is
unavailable, tell me and propose an alternative. Prefer simple, explainable solutions over clever ones. Keep
every claim the UI makes traceable to computed data or a cited crop-table source. After each phase: run the
Streamlit app, run all tests, run `ruff`, fix every error, then stop and report.
