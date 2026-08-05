# Data Science Handoff Contract

This is the exact contract for the person preparing CitySense data. Agree on a delivery date outside this repository; no deadline or approval is fabricated here.

## Required deliverables

Deliver UTF-8 CSV files using these exact names and paths:

```text
data/processed/sensor_locations.csv
data/processed/pedestrian_readings.csv
data/processed/sensor_historical_profiles.csv
data/processed/refuges.csv
```

Use the exact header order in `data/templates/*.csv.example`. Field definitions and allowed values are in `docs/DATA_DICTIONARY.md`.

Do not rename, reorder, add, or remove fields without an agreed schema/API change. A data-version change does not by itself authorise a contract change.

Exact headers:

```text
sensor_locations.csv
location_id,sensor_name,latitude,longitude,location_type,status,data_source,updated_at

pedestrian_readings.csv
location_id,sensed_at,direction_1,direction_2,total_count,interval_minutes,source,fetched_at

sensor_historical_profiles.csv
location_id,day_of_week,hour_of_day,mean_count,median_count,percentile_80,std_dev,sample_count,generated_at,source_period_start,source_period_end,data_version

refuges.csv
refuge_id,name,latitude,longitude,refuge_type,indoor_outdoor,has_seating,is_shaded,lighting_level,opening_hours,short_description,verified,data_source,last_checked_at
```

For every delivery, also provide outside the CSVs:

- source dataset name and public URL;
- retrieval/query date and covered date range;
- licence/attribution requirements;
- transformation script/version and method notes;
- confirmed count unit and interval semantics;
- known missing periods, sensor changes, exclusions, and quality limitations;
- contact for resolving validation errors.

Do not deliver personal location data, addresses searched by users, location histories, disability information, user sensory reports, keys, passwords, or database URLs.

## Historical profile preparation

- Convert source times explicitly to `Australia/Melbourne`, including daylight-saving changes.
- Group by sensor, Melbourne weekday (Monday = 0), and Melbourne hour (0–23).
- Supply mean, median, 80th percentile, standard deviation, sample count, source date range, generation timestamp, and `data_version`.
- Perform and report held-out validation outside the application repository. Do not invent a validation score when an appropriate holdout is unavailable.
- Do not fill absent groups with zero. Missing groups must remain absent so the application returns NO_DATA/unavailable.
- Do not publish a baseline until the pedestrian count interval has been confirmed.

## Validation before handoff

From the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\validate_data.py --all
.\.venv\Scripts\python.exe scripts\load_data.py --dry-run --strict
```

Both commands must exit 0 and every expected dataset must have a non-zero row count. Attach the console output to the team handoff record; do not add real data to Git.

## Error feedback loop

The application developer returns the dataset name, row number, field, and safe validator message. The data preparer corrects the source transformation and issues a new method version where meaning changed. Do not patch invalid production values manually in the database.

## Load and acceptance

After approval, an authorised developer runs:

```powershell
.\.venv\Scripts\python.exe scripts\load_data.py --strict
```

Then confirm `/api/data/status`, one route with matching profiles, and one route with missing profiles. Acceptance requires that missing data remains unavailable/NO_DATA and that repeated loads do not create duplicates.

## Responsibility boundary

The Data Science team downloads and cleans raw data, validates sensor identifiers, confirms count units, creates historical profiles, performs held-out validation, supplies processed CSVs plus provenance metadata, and proposes empirically calibrated confidence/band thresholds.

Flask validates and loads approved files, performs route-to-sensor spatial matching, estimates segment arrival times, reads the profile for the estimated Melbourne weekday/hour, converts `median_count` with the existing count-to-band function, calculates prototype confidence from `sample_count`, `mean_count`, and `std_dev`, scores routes, and returns plain JSON.

Vue submits confirmed user inputs and timezone-aware departure time, then displays backend results. Vue does not calculate bands, confidence, route scoring, or historical profiles.
