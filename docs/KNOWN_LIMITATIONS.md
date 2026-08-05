# Known Limitations

## Sensory interpretation

- Pedestrian density is only one possible sensory factor. CitySense does not currently measure noise, lighting, construction, traffic, smell, weather, surface quality, or individual sensory needs.
- LOW means within the selected observed pedestrian threshold. It is not a guarantee that a place feels quiet or safe.
- Sensor matching uses a simple distance threshold and can associate a nearby sensor with the wrong street corridor.
- Count thresholds and the 180 metre matching distance require real-world calibration.

## Missing data

- NO_DATA never means LOW.
- Sensor coverage is incomplete, and some route sections can have no nearby sensor.
- Fallback pedestrian records are local samples without a live timestamp.
- Historical prediction remains unavailable until validated profile rows are loaded. The repository contains no real profile dataset and fabricates no prediction records.
- When profiles are loaded, the baseline is an explainable weekday/hour median rather than a real-time forecasting model. Prototype confidence thresholds based on sample size and variability require empirical calibration.
- Daylight-saving conversion and source interval semantics must be confirmed during the data-science handoff.

## Routing and navigation

- Prototype fallback routes are generated lines, not verified walking routes.
- Real turn instructions are available only when OpenRouteService returns them.
- Current remaining-time estimates scale the original route time by remaining distance; they do not account for walking speed changes.
- Arrival uses a configurable radius and cannot identify an exact building entrance.
- Off-route detection is approximate. Rerouting remains under user control.
- Active monitoring checks about once per minute and can be delayed by network or free-tier cold starts.

## Refuge information

- The four refuge records are curated prototype data.
- They are not officially verified, guaranteed quiet, guaranteed safe, or guaranteed open.
- Displayed distance is straight-line distance unless a real walking route is explicitly requested. The current Refuge Finder does not calculate refuge walking time.

## Hosting and external services

- Render free services can sleep and have cold starts.
- Neon serverless PostgreSQL can sleep; connection pre-ping reduces stale-connection failures but does not remove wake-up delay.
- HeiGIT, City of Melbourne data, Neon, Render, and OpenStreetMap availability are outside CitySense control.
- No stable production URL has been recorded in this repository.

## Privacy

- Current browser location is held in frontend memory and is not stored or logged by CitySense.
- A route or monitoring request necessarily sends the validated route coordinates to the Flask server for the immediate request. The application does not save those coordinates.
- Route search metadata stores source categories and selected route IDs only.

## Data operations

- The exact completeness and interval semantics of the City “past-hour counts per minute” aggregate cannot be proven by the current application query alone. Live refreshes are therefore not persisted as historical readings.
- Database-first sensor locations and refuges are used only when their tables contain validated rows; otherwise explicit live API or prototype/fallback sources remain visible.
- The schema initializer creates tables and adds current nullable route-search metadata columns, but future breaking schema changes will require a versioned migration tool.

CitySense is decision support, not a guarantee of safety, accessibility, comfort, or service availability.
