# CitySense

CitySense is a Vue and Flask web application for planning sensory-aware walking routes in Melbourne CBD. It combines walking directions with pedestrian sensor data to compare fastest and lower-load route options, support navigation, and locate nearby prototype refuges.

## Main features

- Confirmed address autocomplete and browser current location
- OpenRouteService walking routes with prototype fallback routes
- Fastest, calmest, and crowd-tolerance-based recommendations
- LOW, MODERATE, HIGH, and NO_DATA segment classification
- Leaflet navigation with route steps, follow mode, rerouting, and arrival detection
- Live pedestrian monitoring with a 60-second in-memory cache
- Refuge Finder and Overwhelm Mode
- Optional historical-profile predictions when validated data is loaded

## Technology stack

- Frontend: Vue 3, JavaScript, Vite, Leaflet
- Backend: Python 3.12, Flask, SQLAlchemy, httpx
- Database: SQLite for local development; PostgreSQL on Neon for production
- External services: HeiGIT Pelias, OpenRouteService, City of Melbourne Open Data
- Deployment: Docker, Gunicorn, Render

## Repository structure

```text
backend/       Flask API, models, repositories, services, and tests
frontend/      Vue application and frontend tests
scripts/       Database initialization and data loading tools
data/          CSV contracts and ignored local data directories
docs/          API, deployment, and data documentation
application.py Gunicorn entry point
Dockerfile     Production image
render.yaml    Render service definition
```

## Local setup

Requirements: Python 3.12, Node.js 22, and Corepack.

From the repository root in Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m backend.app
```

In a second PowerShell terminal:

```powershell
cd frontend
corepack enable
pnpm install --frozen-lockfile
pnpm run dev
```

Open `http://127.0.0.1:5173`.

To run the combined production-style application locally:

```powershell
cd frontend
pnpm run build
cd ..
.\.venv\Scripts\python.exe -m backend.app
```

Open `http://127.0.0.1:5000`.

## Environment variables

Backend variables are configured in the ignored root `.env` file. Start from [.env.example](.env.example).

| Variable | Purpose |
| --- | --- |
| `OPENROUTESERVICE_API_KEY` | Server-side key for Pelias autocomplete and OpenRouteService. |
| `DATABASE_URL` | PostgreSQL connection URL. Leave empty to use local SQLite. |
| `USE_LIVE_CITY_DATA` | Enable City of Melbourne live pedestrian data. |
| `REQUEST_TIMEOUT_SECONDS` | Timeout for external HTTP requests. |
| `ALLOWED_ORIGINS` | Comma-separated trusted frontend origins for CORS. |
| `FLASK_DEBUG` | Enable Flask debug mode locally. Keep disabled in production. |
| `ENABLE_DEMO_AUTH` | Enable the shared expo password gate. Keep `false` locally. |
| `DEMO_ACCESS_PASSWORD_HASH` | Werkzeug password hash for demo access; never store the plaintext password. |
| `SESSION_SECRET_KEY` | Random secret used to sign Flask session cookies. |
| `PORT` | Flask or Gunicorn port. |
| `PYTHONUNBUFFERED` | Enable unbuffered Python logs in production. |
| `PREDICTION_MEDIUM_MIN_SAMPLES` | Minimum samples for MEDIUM prediction confidence. |
| `PREDICTION_HIGH_MIN_SAMPLES` | Minimum samples for HIGH prediction confidence. |
| `PREDICTION_MEDIUM_MAX_CV` | Maximum coefficient of variation for MEDIUM confidence. |
| `PREDICTION_HIGH_MAX_CV` | Maximum coefficient of variation for HIGH confidence. |
| `PREDICTION_MIN_ALERT_CONFIDENCE` | Minimum confidence required for a prediction alert. |

Frontend development variables are documented in [frontend/.env.example](frontend/.env.example).

## Running tests

Backend:

```powershell
.\.venv\Scripts\python.exe -m compileall -q backend application.py scripts
.\.venv\Scripts\python.exe -m pytest backend\tests -q
.\.venv\Scripts\python.exe -m pip check
```

Frontend:

```powershell
cd frontend
pnpm run test
pnpm run build
```

## Deployment

The production target is one Render Docker Web Service connected to Neon PostgreSQL. Flask serves the built Vue application and `/api` routes from the same origin.

See [docs/DEPLOY_RENDER_NEON.md](docs/DEPLOY_RENDER_NEON.md) for setup, environment variables, schema initialization, data loading, and smoke tests.

Security configuration and verification are documented in [docs/SECURITY.md](docs/SECURITY.md).
