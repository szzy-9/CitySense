# CitySense

## Overview

CitySense is a sensory-aware walking-route prototype for Melbourne. It helps a user compare walking routes using observed pedestrian load, rather than assuming the shortest route is always the most comfortable.

CitySense is decision support only. Pedestrian density is not a complete measure of sensory conditions, and the application cannot guarantee that a route is quiet, accessible, open, or safe.

## Current User Experience

CitySense has three main screens:

1. **Plan** — confirm a start and destination, choose a crowd tolerance, and compare Fastest, Calmest, and Recommended routes.
2. **Navigate** — view the selected route, segment load, current position, route instruction, remaining distance, monitoring alerts, and manual rerouting controls.
3. **Overwhelm Mode** — show one nearest prototype refuge with a straight-line distance and direction.

The Plan screen also contains a separate **Find a Quiet Place** tool. It can list several nearby prototype refuges without requiring a planned route.

## Current Features

- HeiGIT Pelias address autocomplete through Flask.
- Confirmed address results and browser Current Location.
- HeiGIT OpenRouteService walking routes with alternatives and turn-by-turn steps.
- Clearly labelled prototype routes when live routing is unavailable.
- Live City of Melbourne pedestrian counts with a local fallback file.
- LOW, MODERATE, HIGH, and NO_DATA segment bands.
- Peak-load scoring: the route score uses the worst observed segment, not the average.
- Fastest, Calmest, and crowd-threshold-based Recommended routes.
- A visible LOW, HIGH, or NO_DATA route indicator.
- Confidence labels and reasons based on route source, data freshness, sensors, and coverage.
- Optional explainable historical median outlook when validated sensor profiles have been loaded; otherwise the UI states that prediction is unavailable.
- Leaflet map with route segments, sensors, prototype refuges, current position, and location accuracy.
- Follow Mode, Re-centre, arrival detection, off-route detection, and manual rerouting.
- Periodic active-route crowd monitoring without requesting a new ORS route on every position update.
- Prototype refuge finder and Overwhelm Mode.
- SQLite for local development and Neon PostgreSQL support for production.
- Validated CSV contracts, idempotent SQLite/PostgreSQL upserts, database-first sensor/refuge records, and safe data-status reporting.
- Flask serves both the built Vue interface and API from one process.

## Data Meaning

- **LIVE** means the response used a live external service at request time or a short-lived cache of live pedestrian data.
- **PROTOTYPE** means route geometry was generated locally and is not a real walking route.
- **FALLBACK** means local sample pedestrian data was used.
- **NO_DATA** means there is not enough reliable observed data. It never means Low or quiet.

Refuge records are small, curated prototype records. They are not officially verified sensory refuges.

## Architecture

Target production flow:

```text
Browser
  -> Vue 3 + Leaflet
  -> Flask API on one Render Web Service
      -> HeiGIT Pelias autocomplete
      -> HeiGIT OpenRouteService directions
      -> City of Melbourne pedestrian API
      -> Neon PostgreSQL
```

Production browser requests use relative `/api` URLs. The API key and database URL remain on the server.

AWS Elastic Beanstalk files remain as legacy/deferred material. Render and Neon are the active deployment target for this build. No deployed URL is claimed in this repository.

## Local Setup on Windows PowerShell

From `D:\CitySense`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and set:

```env
OPENROUTESERVICE_API_KEY=YOUR_HEIGIT_KEY
```

Leave `DATABASE_URL` empty to use local SQLite.

Start Flask:

```powershell
python -m backend.app
```

In a second PowerShell terminal:

```powershell
cd D:\CitySense\frontend
corepack enable
pnpm install --frozen-lockfile
pnpm run dev
```

Open `http://127.0.0.1:5173`.

To test the combined production-style application locally:

```powershell
cd D:\CitySense\frontend
pnpm run build
cd ..
.\.venv\Scripts\python.exe -m backend.app
```

Then open `http://127.0.0.1:5000`.

## Environment Variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `OPENROUTESERVICE_API_KEY` | Yes for live search/routes | Server-side HeiGIT key. |
| `DATABASE_URL` | Production | Neon pooled PostgreSQL URL with `sslmode=require`. Empty uses local SQLite. |
| `USE_LIVE_CITY_DATA` | No | Enables the City of Melbourne live API. Default: `true`. |
| `REQUEST_TIMEOUT_SECONDS` | No | External request timeout. |
| `ALLOWED_ORIGINS` | Cross-origin only | Comma-separated trusted frontend origins. Production same-origin can leave it empty. |
| `PORT` | No | Flask/Gunicorn port. Render supplies this value. |
| `FLASK_DEBUG` | No | Keep `false` in production. |
| `PYTHONUNBUFFERED` | Production | Sends Python logs directly to Render logs. |
| `VITE_API_BASE_URL` | Frontend development only | Local Flask URL. Production should be blank for same-origin `/api`. |
| `VITE_ARRIVAL_DISTANCE_METERS` | No | Arrival radius. Default: 35 metres. |
| `PREDICTION_MEDIUM_MIN_SAMPLES` | No | Prototype minimum samples for Medium prediction confidence. |
| `PREDICTION_HIGH_MIN_SAMPLES` | No | Prototype minimum samples for High prediction confidence. |
| `PREDICTION_MEDIUM_MAX_CV` | No | Prototype Medium-confidence variability limit. |
| `PREDICTION_HIGH_MAX_CV` | No | Prototype High-confidence variability limit. |
| `PREDICTION_MIN_ALERT_CONFIDENCE` | No | Minimum `MEDIUM` or `HIGH` confidence for a predictive alert; invalid/LOW values are safely treated as MEDIUM. |

## Testing

Backend:

```powershell
.\.venv\Scripts\python.exe -m compileall -q backend application.py scripts
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

Frontend:

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm run test
pnpm run build
```

Live third-party calls are not part of CI. CI uses fake clients and fallback data.

## Data Preparation

No real historical CSV is committed. Header-only contracts are in `data/templates/`, ignored production paths are under `data/processed/`, and fictional tests are under `tests/fixtures/data/`.

```powershell
.\.venv\Scripts\python.exe scripts\validate_data.py --all
.\.venv\Scripts\python.exe scripts\load_data.py --dry-run --strict
.\.venv\Scripts\python.exe scripts\load_data.py --strict
```

See [data/README.md](data/README.md), [Data Dictionary](docs/DATA_DICTIONARY.md), [Data Pipeline](docs/DATA_PIPELINE.md), and [Data Science Handoff](docs/DS_DATA_HANDOFF.md).

## Deployment

See [docs/DEPLOY_RENDER_NEON.md](docs/DEPLOY_RENDER_NEON.md). The repository includes `Dockerfile`, `.dockerignore`, and `render.yaml` for one Render Web Service.

## Privacy and Security

- `.env` is ignored by Git.
- API keys and database credentials are not sent to Vue.
- Precise browser location stays in frontend memory and is not stored or logged.
- Route-search storage contains source categories and selected route IDs, not complete addresses or coordinates.
- External service errors are converted to safe user-facing messages.
- No external data is rendered with `v-html`.

## Known Limitations

See [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md). Important limitations include incomplete sensor coverage, unverified refuge data, prototype fallbacks, Render free-tier cold starts, and unavailable historical prediction until validated baselines are loaded.

## Licence and Attribution

No software licence has been selected yet.

- Map tiles and map attribution: OpenStreetMap contributors.
- Route and autocomplete services: HeiGIT / openrouteservice / Pelias, subject to their service terms.
- Pedestrian information: City of Melbourne open data, subject to the dataset attribution and licence terms.
