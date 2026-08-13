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
DEMO_ACCESS_PASSWORD_HASH
SESSION_SECRET_KEY
```

Production settings:

```text
FLASK_ENV=production
FLASK_DEBUG=false
PYTHONUNBUFFERED=1
USE_LIVE_CITY_DATA=true
REQUEST_TIMEOUT_SECONDS=8
ENABLE_DEMO_AUTH=true
ALLOWED_ORIGINS=https://YOUR_RENDER_SERVICE.onrender.com
PREDICTION_MEDIUM_MIN_SAMPLES=12
PREDICTION_HIGH_MIN_SAMPLES=30
PREDICTION_MEDIUM_MAX_CV=1.0
PREDICTION_HIGH_MAX_CV=0.5
PREDICTION_MIN_ALERT_CONFIDENCE=MEDIUM
```

Use the final Render HTTPS origin for `ALLOWED_ORIGINS`. Do not use localhost or
`*` in production. The Blueprint marks this value as manually configured so a
repository file does not guess the deployed hostname.

Generate the password hash locally without putting the plaintext password in a
file:

```powershell
.\.venv\Scripts\python.exe -c "from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass('Demo password: ')))"
```

Store only the printed hash as `DEMO_ACCESS_PASSWORD_HASH`. Generate an
independent random session secret:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Store that value as `SESSION_SECRET_KEY`. Render supplies `PORT`. Do not store
secret values in `render.yaml` or Git.

The Render health check at `/api/health` remains public. The application and
other API endpoints require the demo password when `ENABLE_DEMO_AUTH=true`.
Logout is available through `POST /logout`.

## Neon runtime role

The deployed Flask process only reads DS-managed `citysense` tables, so its
dedicated runtime database role can be SELECT-only. Grant that role only:

- connection access to the selected Neon database;
- `USAGE` on the `citysense` schema;
- `SELECT` on the specific `citysense` tables used by the application.

Do not give the runtime role table creation, schema modification, or data-write
permissions. Keep DS loading/admin credentials separate and use them only from
trusted administrative workflows. Configure the runtime role's pooled Neon URL,
including `sslmode=require`, as Render's `DATABASE_URL`. These permission
changes must be made manually by the Neon/DS administrator; deployment does not
alter them.

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

Check the public health endpoint, then authenticate before checking data status:

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
