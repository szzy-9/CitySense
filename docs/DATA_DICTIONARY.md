# CitySense Data Dictionary

All CSV files use UTF-8, a single header row, comma separators, ISO dates, and timezone-aware ISO 8601 timestamps. Empty text is allowed only for fields marked optional. IDs are source identifiers or stable project identifiers; they must not contain personal location history.

CSV coordinates are separate `latitude` then `longitude` columns in WGS84 decimal degrees. Do not put `[longitude, latitude]` arrays into CSV fields. Use an empty field for an allowed null; do not write `0`, `LOW`, `NO_DATA`, `null`, `N/A`, or an invented value to represent missing data. Timestamps must include `Z` or a numeric offset and profile grouping must use `Australia/Melbourne`, including daylight-saving changes.

## `sensor_locations`

Primary key: `location_id`.

| Field | Type | Required | Meaning and validation |
| --- | --- | --- | --- |
| `location_id` | text, max 80 | Yes | Stable sensor-location identifier. |
| `sensor_name` | text, max 200 | Yes | Public location name or description from the source. |
| `latitude` | decimal | Yes | WGS84 latitude, -90 to 90. Runtime route inputs are separately restricted to Melbourne. |
| `longitude` | decimal | Yes | WGS84 longitude, -180 to 180. |
| `location_type` | text, max 80 | No | Source-provided location category. |
| `status` | text, max 30 | No | For example `active`; runtime DB precedence uses active or blank records. |
| `data_source` | text, max 80 | No | Data provenance, not an API key. |
| `updated_at` | timestamp with offset | No | When the source location record was updated. |

## `pedestrian_readings`

Database primary key: generated `reading_id`. Import uniqueness: `location_id + sensed_at + interval_minutes + source`. `location_id` must exist in `sensor_locations`.

| Field | Type | Required | Meaning and validation |
| --- | --- | --- | --- |
| `location_id` | text | Yes | Sensor-location foreign key. |
| `sensed_at` | timestamp with offset | Yes | Start or representative time defined by the supplying dataset. |
| `direction_1` | integer >= 0 | No | Source direction-one count. Blank means missing, not zero. |
| `direction_2` | integer >= 0 | No | Source direction-two count. Blank means missing, not zero. |
| `total_count` | integer | Yes | Non-negative count for the stated interval. |
| `interval_minutes` | integer | Yes | Positive interval length supplied by the data preparer. |
| `source` | text, max 80 | Yes | Dataset/version provenance. |
| `fetched_at` | timestamp with offset | Yes | When this record was retrieved or produced. |

Important unit blocker: the current live City of Melbourne query sums `total_of_directions` records returned by the “past-hour counts per minute” dataset. Its normalised in-memory reading labels the rolling dataset window as `interval_minutes=60`, but the code cannot independently prove that every minute is present or that the sum is a complete hourly observation. Live refreshes therefore remain an in-memory snapshot and are not written into `pedestrian_readings`. A data owner must confirm interval completeness and aggregation semantics before producing a comparable CSV. Existing LOW/MODERATE/HIGH thresholds are prototype count thresholds and require calibration against the confirmed interval.

## `sensor_historical_profiles`

Composite primary key: `location_id + day_of_week + hour_of_day`. `location_id` must exist in `sensor_locations`.

| Field | Type | Required | Meaning and validation |
| --- | --- | --- | --- |
| `location_id` | text | Yes | Sensor-location foreign key. |
| `day_of_week` | integer 0–6 | Yes | Python convention: Monday = 0, Sunday = 6, using Melbourne local time. |
| `hour_of_day` | integer 0–23 | Yes | Start hour in Australia/Melbourne local time. |
| `mean_count` | decimal >= 0 | Yes | Arithmetic mean for the group. |
| `median_count` | decimal >= 0 | Yes | Median used by runtime prediction. |
| `percentile_80` | decimal >= 0 | Yes | 80th percentile supplied for analysis; not stored as a permanent band. |
| `std_dev` | decimal >= 0 | Yes | Standard deviation used for confidence. |
| `sample_count` | integer >= 0 | Yes | Number of observations in the group. |
| `generated_at` | timestamp with offset | Yes | Reproducible profile-build time. |
| `source_period_start` | ISO date | Yes | First source date. |
| `source_period_end` | ISO date | Yes | Last source date; cannot precede start. |
| `data_version` | text, max 40 | Yes | Version of the data preparation method and output. |

Prediction uses the median for a matched sensor, weekday, and ETA hour. The route peak is the highest predicted segment band. Confidence thresholds are configurable prototypes based on sample count and coefficient of variation; they have not been empirically calibrated.

## `refuges`

Primary key: `refuge_id`.

| Field | Type | Required | Meaning and validation |
| --- | --- | --- | --- |
| `refuge_id` | text, max 80 | Yes | Stable project/source identifier. |
| `name` | text, max 160 | Yes | Display name. |
| `latitude`, `longitude` | decimal | Yes | WGS84 coordinates in valid global ranges. |
| `refuge_type` | text, max 80 | Yes | Short category. |
| `indoor_outdoor` | text, max 40 | No | Source classification; blank means unknown. |
| `has_seating` | boolean | No | `true/false`, `1/0`, or `yes/no`; blank means unknown. |
| `is_shaded` | boolean | No | Same boolean formats; blank means unknown. |
| `lighting_level` | text, max 80 | No | Source-provided plain-text description. |
| `opening_hours` | text, max 200 | No | Source-provided availability note, never proof the location is currently open. |
| `short_description` | text, max 300 | Yes | Plain text attributes; no HTML. |
| `verified` | boolean | No | Same boolean formats; blank defaults to false. False is never official verification. |
| `data_source` | text, max 80 | No | Provenance of the refuge record. |
| `last_checked_at` | timestamp with offset | No | Last source review time, not a live-open status. |

## `route_searches`

This table stores operational metadata only. It does not store labels, full addresses, coordinates, route geometry, location history, disability data, sensory reports, or performance timings.

Stored fields include start/end source category, fastest/calmest route IDs, route and pedestrian source, selected route type, confidence, candidate count, whether historical prediction was used, prediction confidence, and creation time.
