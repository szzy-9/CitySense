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
  "database": { "status": "connected | degraded" }
}
```

## `GET /api/geocode/autocomplete?q=...`

- Query length: 2–120 characters.
- Maximum results: 5.
- Results are restricted to the configured Melbourne rectangle.
- The browser must use a selected result; typed text alone is not a route location.

## `GET /api/refuges`

Without coordinates, returns the prototype list. With validated `lat`, `lon`, `label`, and `source`, returns a distance-sorted list and `nearest_refuge`.

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
  "crowd_tolerance": "LOW | MEDIUM | HIGH"
}
```

Each returned route includes:

```json
{
  "source": "LIVE | PROTOTYPE",
  "fallback_reason": null,
  "geometry": { "type": "LineString", "coordinates": [] },
  "distance_meters": 1000,
  "duration_minutes": 12.5,
  "steps": [],
  "segments": [],
  "sensory_level": "LOW | MODERATE | HIGH | NO_DATA",
  "peak_load": "LOW | MODERATE | HIGH | NO_DATA",
  "sensory_indicator": "LOW | HIGH | NO_DATA",
  "coverage": 0.75,
  "confidence": "HIGH | LOW",
  "confidence_reasons": [],
  "recommended": true,
  "recommendation_reason": "Explanation",
  "congestion_avoidable": true
}
```

`NO_DATA` is never equivalent to `LOW`.

Tolerance mapping:

- LOW accepts only LOW observed peak.
- MEDIUM accepts LOW or MODERATE.
- HIGH accepts LOW, MODERATE, or HIGH.

The response also includes `recommended_route_id`, `request_settings`, sensor markers, and source/update metadata.

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

