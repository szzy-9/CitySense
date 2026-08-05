# Focused Release Checklist

Record real evidence beside each item before release. Do not mark manual items complete without observing them.

## Input and API behaviour

- [ ] Invalid JSON and missing route fields return HTTP 400 with a safe message.
- [ ] Out-of-bounds coordinates and oversized monitoring geometry are rejected.
- [ ] SQL-injection-like strings are treated as plain search input or rejected by validation; no SQL is assembled by string concatenation.
- [ ] Missing HeiGIT key returns a safe autocomplete error and labelled prototype routes.
- [ ] HeiGIT authentication failure, timeout, and invalid response return labelled fallback routes without external response bodies.
- [ ] Unavailable City data produces explicit fallback status.
- [ ] Unavailable database produces degraded health or a safe 503 with rollback.

## Privacy and secrets

- [ ] `.env` is ignored and not tracked.
- [ ] Secret scan finds no real API key, database URL, password, or token in tracked files.
- [ ] Browser network inspection shows no API key or database URL sent to Vue.
- [ ] Application logs contain no precise current-position coordinates.
- [ ] Database inspection confirms no full address, precise coordinate, location history, disability data, sensory report, or performance timing is stored.

## Route meaning

- [ ] Every route card shows a text and visual sensory indicator without expansion.
- [ ] NO_DATA is displayed as No Data and never Low.
- [ ] Prototype and fallback results are clearly labelled with a reason.
- [ ] Above-threshold routes are not selected by default when a reliable below-threshold route exists.
- [ ] Unavoidable and insufficient-data cases use their specific explanation.
- [ ] Current observed load and historical outlook are visually and textually distinct.
- [ ] Missing historical profiles display unavailable/NO_DATA, never zero or Low.
- [ ] Predictive alerts appear only for 5–60 minute, above-threshold, sufficiently confident cases.

## Data handoff and database

- [ ] `validate_data.py --all` and `load_data.py --dry-run --strict` pass on approved non-empty files.
- [ ] Count interval semantics, timezone, date range, method version, and attribution are documented by the data owner.
- [ ] Repeated data loads are idempotent and a failed dataset transaction rolls back.
- [ ] `/api/data/status` matches the database without exposing rows or credentials.
- [ ] Live City refreshes remain in memory and are not written as historical observations.

## Navigation and accessibility

- [ ] Main actions work with keyboard only and focus is visible.
- [ ] Manual map movement pauses Follow Mode and Re-centre restores it.
- [ ] Exiting Navigate clears the geolocation watcher and monitor interval.
- [ ] Position updates do not automatically request ORS routes.
- [ ] Reduced-motion preference is respected.
- [ ] Current Location works only after permission and HTTPS/localhost requirements are met.

## Dependencies and deployment

- [ ] Python compile check and pytest pass.
- [ ] `python -m pip check` passes.
- [ ] Frontend tests and production build pass.
- [ ] Dependency audit results are reviewed; do not claim zero vulnerabilities without running the tools.
- [ ] Docker image builds and starts in an environment with Docker available.
- [ ] Render health endpoint is tested over HTTPS.
- [ ] Neon connection uses the pooled URL and `sslmode=require`.
- [ ] Leaflet tiles, autocomplete, directions, pedestrian data, monitoring, reroute, and SPA refresh work on the deployed URL.
