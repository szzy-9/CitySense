# Render and Neon deployment

CitySense deploys as one Render Docker Web Service with a Neon PostgreSQL database.

## Create the Neon database

1. Create a Neon project and database.
2. Create a least-privilege application role.
3. Copy the pooled PostgreSQL connection string.
4. Confirm the connection string includes `sslmode=require`.
5. Store the connection string as `DATABASE_URL` in Render.

## Create the Render service

1. Connect the GitHub repository to Render.
2. Create a Blueprint from `render.yaml`.
3. Confirm that Render detects the `citysense` Docker Web Service.
4. Configure the environment variables below.
5. Deploy the service.

The container builds the Vue frontend with Node 22, installs the Python dependencies, and starts Gunicorn with:

```text
gunicorn application:application --bind 0.0.0.0:${PORT:-10000} --workers 2 --threads 2
```

## Environment variables

Required secrets:

```text
OPENROUTESERVICE_API_KEY
DATABASE_URL
```

Production settings:

```text
FLASK_ENV=production
FLASK_DEBUG=false
PYTHONUNBUFFERED=1
USE_LIVE_CITY_DATA=true
REQUEST_TIMEOUT_SECONDS=8
ALLOWED_ORIGINS=
PREDICTION_MEDIUM_MIN_SAMPLES=12
PREDICTION_HIGH_MIN_SAMPLES=30
PREDICTION_MEDIUM_MAX_CV=1.0
PREDICTION_HIGH_MAX_CV=0.5
PREDICTION_MIN_ALERT_CONFIDENCE=MEDIUM
```

Render supplies `PORT`. Do not store secret values in `render.yaml` or Git.

## Load approved data

The Render filesystem is ephemeral. Load approved CSV files from a trusted workstation or one-off environment with `DATABASE_URL` configured securely.

```text
python scripts/validate_data.py --all
python scripts/load_data.py --dry-run --strict
python scripts/load_data.py --strict
```

For staged imports, load sensor locations before dependent readings or profiles:

```text
python scripts/load_data.py --sensor-locations data/processed/sensor_locations.csv --strict
python scripts/load_data.py --pedestrian-readings data/processed/pedestrian_readings.csv --strict
python scripts/load_data.py --historical-profiles data/processed/sensor_historical_profiles.csv --strict
python scripts/load_data.py --refuges data/processed/refuges.csv --strict
```

## Verify the deployment

Check the health and data-status endpoints:

```text
https://YOUR_RENDER_SERVICE.onrender.com/api/health
https://YOUR_RENDER_SERVICE.onrender.com/api/data/status
```

Smoke-test the following:

1. The Vue interface loads at `/`.
2. Address autocomplete returns selectable results.
3. Route requests return live or explicitly labelled prototype routes.
4. Route cards display sensory indicators and confidence.
5. Leaflet tiles load over HTTPS.
6. Current Location works over HTTPS.
7. SPA routes reload without a 404 response.
