# CitySense Data Pipeline

## Principles

- Real raw and processed datasets stay outside Git.
- Header-only `.csv.example` files document contracts and are never auto-loaded.
- Automated tests use only fictional `SYNTH-*` fixtures.
- Validation happens before any database transaction.
- Each dataset loads in its own transaction. An error rolls back that dataset.
- Upserts make repeated approved loads idempotent on SQLite and PostgreSQL.
- The live pedestrian refresh uses a 60-second in-memory cache and is not persisted.

## Prepare files

Place approved deliverables at the exact paths documented in `data/README.md`. Keep original extracts in `data/raw/` only on an authorised local machine. A preprocessing process may write contract-compliant CSV files to `data/processed/`; the application does not invent missing values.

## Validate

```powershell
.\.venv\Scripts\python.exe scripts\validate_data.py --all
```

The validator checks exact headers, required fields, types, coordinate/count/hour/day ranges, booleans, timezone-aware timestamps, source-period order, duplicate natural keys, and cross-file sensor foreign keys. It prints a row count plus row-numbered errors and returns a non-zero exit code on failure.

Validate one explicit file:

```powershell
.\.venv\Scripts\python.exe scripts\validate_data.py --sensor-locations data\processed\sensor_locations.csv
```

A valid header-only file produces a zero-row warning. It is not considered loadable by the loader.

## Dry-run and load

```powershell
.\.venv\Scripts\python.exe scripts\load_data.py --dry-run --strict
.\.venv\Scripts\python.exe scripts\load_data.py --strict
```

Without `--strict`, missing optional standard files are reported and skipped. Explicitly selected missing files and strict-mode missing files fail. If no non-empty dataset is available, the loader exits non-zero and never reports an empty success.

Example templates are rejected by the loader even if passed explicitly.

## Runtime precedence

1. Sensor locations: validated database rows when populated; otherwise the live City location API; finally local fallback locations when live pedestrian retrieval fails.
2. Live pedestrian counts: City API or the 60-second in-memory cache; local fallback JSON on failure. Refreshes are not inserted into the database.
3. Historical profiles: database only. Missing rows return `Historical prediction unavailable` with no fake count.
4. Refuges: validated database rows when populated; otherwise curated, unverified prototype records.
5. Route-search metadata: database only; no addresses or coordinates are recorded.

## Safe rollback and verification

On a database exception, the loader and application call rollback and return a short error without SQL or connection details. After loading, verify counts with:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/data/status
```

The endpoint returns booleans and row counts only. It does not expose credentials or connection strings.
