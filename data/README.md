# CitySense data directories

This directory defines the handoff boundary between data preparation and the application.

- `raw/` is for local source extracts. Its contents are ignored by Git.
- `processed/` is for validated production-ready CSV files. Its contents are ignored by Git.
- `templates/` contains header-only examples. Files ending in `.csv.example` are documentation only and are never auto-loaded.
- Synthetic automated-test data belongs only in `tests/fixtures/data/`.

Do not commit real production extracts, personal location data, API keys, database URLs, or invented historical baselines.

Expected processed filenames:

```text
data/processed/sensor_locations.csv
data/processed/pedestrian_readings.csv
data/processed/sensor_historical_profiles.csv
data/processed/refuges.csv
```

Validate without writing to the database:

```powershell
.\.venv\Scripts\python.exe scripts\validate_data.py --all
.\.venv\Scripts\python.exe scripts\load_data.py --dry-run --strict
```

Load approved files with dataset-level transactions and idempotent upserts:

```powershell
.\.venv\Scripts\python.exe scripts\load_data.py --strict
```

See `docs/DATA_DICTIONARY.md`, `docs/DATA_PIPELINE.md`, and `docs/DS_DATA_HANDOFF.md` before preparing or loading data.
