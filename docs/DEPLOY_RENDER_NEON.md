# Deploy CitySense with Render and Neon

This document describes the deployment target. It does not claim that an account, database, deployment, domain, or stable URL has already been created.

## 1. Create the Neon PostgreSQL project

1. Sign in to Neon and create a project in a region near the Render service and Melbourne users where practical.
2. Create or select a database and a least-privilege application role.
3. Open the Neon connection details and choose the **pooled** connection string.
4. Confirm the connection string includes `sslmode=require`.
5. Store the value securely. Do not add it to source code, documentation, screenshots, issues, or chat.

The expected variable name is:

```text
DATABASE_URL
```

SQLAlchemy converts `postgresql://` to the installed psycopg 3 driver and adds `sslmode=require` if it is missing.

## 2. Create the Render Web Service

1. Push the reviewed project to the intended private or public GitHub repository using the team's normal process. Codex does not push it.
2. In Render, choose **New > Blueprint** and select the repository containing `render.yaml`.
3. Confirm that Render detects one Docker Web Service named `citysense`.
4. Keep the free plan only if its cold-start and availability limits are acceptable.
5. Keep automatic deployment disabled until acceptance testing is complete.

The Docker image performs two stages:

1. Node 22 installs the locked pnpm dependencies and builds Vue.
2. Python 3.12 installs Flask/Gunicorn, copies the Vue build, and starts one combined service.

The container start command is:

```text
gunicorn application:application --bind 0.0.0.0:${PORT:-10000} --workers 2 --threads 2
```

## 3. Configure Render environment variables

Set these in the Render dashboard. Do not put their real values in `render.yaml`.

Required secrets:

```text
OPENROUTESERVICE_API_KEY
DATABASE_URL
```

Required production settings:

```text
FLASK_ENV=production
FLASK_DEBUG=false
PYTHONUNBUFFERED=1
USE_LIVE_CITY_DATA=true
REQUEST_TIMEOUT_SECONDS=8
PREDICTION_MEDIUM_MIN_SAMPLES=12
PREDICTION_HIGH_MIN_SAMPLES=30
PREDICTION_MEDIUM_MAX_CV=1.0
PREDICTION_HIGH_MAX_CV=0.5
PREDICTION_MIN_ALERT_CONFIDENCE=MEDIUM
```

Same-origin production normally uses:

```text
ALLOWED_ORIGINS=
```

If a separate trusted frontend is introduced later, set `ALLOWED_ORIGINS` to an explicit comma-separated list. Do not use `*`.

Render supplies `PORT` automatically.

## 4. Deploy

1. Trigger the first manual deploy.
2. Watch the Docker build log for the Vue build, Python dependency installation, and Gunicorn startup.
3. Do not paste full environment dumps into support tickets.
4. A database connection failure should produce a degraded health result without revealing the connection string.

## 5. Initialize or verify the schema

Application startup calls the idempotent SQLAlchemy `create_all` operation. To verify explicitly, use a secure Render Shell if available:

```text
python scripts/init_db.py
```

Alternatively, run the script locally only after temporarily setting `DATABASE_URL` in the local ignored `.env`. Never put the URL directly in the command history.

Successful output:

```text
Database schema is ready.
```

The Render filesystem is ephemeral. Do not copy persistent CSV data into the running filesystem. If approved production data must be loaded, run the version-controlled loader from a trusted workstation or one-off environment with `DATABASE_URL` set securely:

```text
python scripts/load_data.py --dry-run --strict
python scripts/load_data.py --strict
```

For a staged first import, keep sensor foreign keys available before dependent profiles/readings:

```text
python scripts/load_data.py --sensor-locations data/processed/sensor_locations.csv --strict
python scripts/load_data.py --historical-profiles data/processed/sensor_historical_profiles.csv --strict
python scripts/load_data.py --refuges data/processed/refuges.csv --strict
```

Keep `data/raw/` and `data/processed/` files out of Git. Confirm loaded state through `/api/data/status`; the endpoint reveals counts only, not database details.

## 6. Health and smoke tests

Replace the placeholder with the actual Render URL:

```text
https://YOUR_RENDER_SERVICE.onrender.com/api/health
```

Expected connected response shape:

```json
{
  "status": "ok",
  "service": "CitySense API",
  "database": { "status": "connected" },
  "data": {
    "sensor_locations": { "loaded": false },
    "pedestrian_readings": { "loaded": false },
    "historical_profiles": { "loaded": false },
    "refuges": { "loaded": false }
  }
}
```

Then manually verify:

1. `/` loads the Vue interface.
2. Address autocomplete returns confirmed results.
3. A route request returns LIVE geometry, or a clearly labelled PROTOTYPE fallback with a reason.
4. Route cards show indicators and confidence.
5. Leaflet/OpenStreetMap tiles load over HTTPS.
6. Current Location is requested only after a user action or entering Navigate.
7. `/api/routes/monitor` does not request a new ORS route.
8. Refreshing a non-API frontend path returns the SPA build.
9. `/api/data/status` matches the datasets actually loaded into Neon.
10. A missing historical profile displays `Historical prediction unavailable` rather than zero or Low.

## 7. Record the stable URL

After real deployment and smoke testing, record it here or in the team release record:

```text
Stable URL: NOT YET RECORDED
Verified by: NOT YET RECORDED
Verification date: NOT YET RECORDED
```

Do not replace these fields without real evidence.

## Legacy AWS material

`Procfile`, `application.py`, and local Elastic Beanstalk configuration remain for compatibility and historical work. They are not the active deployment target for this build and should not be deleted until the team confirms Render/Neon deployment.
