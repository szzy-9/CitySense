# CitySense API Contract

All API errors use a short JSON message:

```json
{ "error": "Safe user-facing message." }
```

Responses never include API keys, database URLs, SQL, external response bodies, or stack traces.

## `GET /api/health`

Reports application and database availability without connection details.

```json
{
  "status": "ok | degraded",
  "service": "CitySense API",
  "database": { "status": "connected | degraded" },
  "data": {
    "sensor_locations": { "loaded": false },
    "pedestrian_readings": { "loaded": false },
    "historical_profiles": { "loaded": false },
    "refuges": { "loaded": false }
  }
}
```

## `GET /api/data/status`

Returns safe database row counts and loaded booleans for the four data tables. It never returns connection details, raw rows, or credentials.

## `GET /api/geocode/autocomplete?q=...`

- Query length: 2–120 characters.
- Maximum results: 5.
- Results are restricted to the configured Melbourne rectangle.
- The browser must use a selected result; typed text alone is not a route location.

## `GET /api/refuges`

Without coordinates, returns the active database list when populated, otherwise the curated prototype list. With validated `lat`, `lon`, `label`, and `source`, returns a distance-sorted list and `nearest_refuge`.

Distances are straight-line distances. Refuge records are unverified prototypes.

## `POST /api/routes`

Request:

```json
{
  "start": {
    "label": "Confirmed label",
    "lat": -37.81,
    "lon": 144.96,
    "source": "autocomplete | heigit_pelias | current_location | reroute"
  },
  "end": {
    "label": "Confirmed label",
    "lat": -37.82,
    "lon": 144.97,
    "source": "autocomplete | heigit_pelias | current_location | reroute"
  },
  "crowd_tolerance": "LOW | MEDIUM | HIGH",
  "departure_time": "2026-08-06T09:30:00+10:00"
}
```

`departure_time` is optional but must include a timezone offset when supplied. When absent, Flask uses the current time in `Australia/Melbourne` and returns `departure_time_defaulted: true` in `request_settings`.

Each returned route includes:

```json
{
  "source": "LIVE | PROTOTYPE",
  "fallback_reason": null,
  "geometry": { "type": "LineString", "coordinates": [] },
  "distance_meters": 1000,
  "duration_minutes": 12.5,
  "steps": [],
  "segments": [
    {
      "predicted_count": 320,
      "predicted_band": "MODERATE",
      "prediction_confidence": "MEDIUM",
      "prediction_basis": "Historical median for the same weekday and hour",
      "predicted_for": "2026-08-06T10:00:00+10:00",
      "profile_sensor_count": 2
    }
  ],
  "sensory_level": "LOW | MODERATE | HIGH | NO_DATA",
  "peak_load": "LOW | MODERATE | HIGH | NO_DATA",
  "sensory_indicator": "LOW | HIGH | NO_DATA",
  "coverage": 0.75,
  "confidence": "HIGH | LOW",
  "confidence_reasons": [],
  "recommended": true,
  "recommendation_reason": "Explanation",
  "congestion_avoidable": true,
  "historical_prediction_available": true,
  "predicted_peak": "LOW | MODERATE | HIGH | NO_DATA",
  "predicted_count": 320,
  "prediction_confidence": "LOW | MEDIUM | HIGH",
  "prediction_basis": "Historical median for the same weekday and hour",
  "prediction_unavailable_reason": null,
  "prediction_alert": {
    "triggered": true,
    "predicted_condition": "HIGH",
    "segment_index": 3,
    "lead_minutes": 25,
    "confidence": "MEDIUM",
    "message": "Historical patterns suggest High crowd levels in about 25 minutes.",
    "reroute_available": true
  }
}
```

When no matching profile exists, prediction is exactly unavailable: `historical_prediction_available=false`, `predicted_peak=NO_DATA`, `predicted_count=null`, `prediction_confidence=LOW`, `prediction_alert=null`, and `prediction_unavailable_reason="Historical profile data has not been loaded."`. No zero or generated value substitutes for missing data.

Prediction uses route-segment ETA, matched sensor ID, Melbourne weekday/hour, and the imported historical median. An alert is present only when the predicted band exceeds tolerance, lead time is 5–60 minutes, and configured confidence is sufficient. Prototype route geometry is limited to LOW prediction confidence and cannot trigger a prediction alert.

`NO_DATA` is never equivalent to `LOW`.

Tolerance mapping:

- LOW accepts only LOW observed peak.
- MEDIUM accepts LOW or MODERATE.
- HIGH accepts LOW, MODERATE, or HIGH.

The response also includes `recommended_route_id`, `request_settings`, sensor markers, and separate route, pedestrian, sensor-location, historical-profile, and refuge source/update metadata.

## `POST /api/routes/monitor`

This endpoint evaluates remaining route geometry against current/cached pedestrian data. It does not call OpenRouteService.

Request:

```json
{
  "coordinates": [[144.96, -37.81], [144.97, -37.82]],
  "crowd_tolerance": "MEDIUM"
}
```

Validation:

- 2–500 points.
- Every point contains numeric longitude and latitude.
- Every point is within the supported Melbourne bounds.
- Request body is limited by Flask configuration.

Response:

```json
{
  "breached": true,
  "upcoming_peak": "HIGH",
  "affected_segment_index": 0,
  "data_source": "LIVE",
  "cache_status": "live | cached | fallback",
  "updated_at": "ISO timestamp",
  "message": "High crowd levels were detected ahead."
}
```
