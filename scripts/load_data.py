"""Validate and upsert approved CitySense CSV datasets."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError

from backend.app import create_app
from backend.database import safe_rollback
from backend.models import (
    PedestrianReading,
    Refuge,
    SensorHistoricalProfile,
    SensorLocation,
    db,
)
from scripts.validate_data import DEFAULT_FILES, HEADERS, validate_dataset


MODELS = {
    "sensor_locations": SensorLocation,
    "pedestrian_readings": PedestrianReading,
    "historical_profiles": SensorHistoricalProfile,
    "refuges": Refuge,
}
CONFLICT_KEYS = {
    "sensor_locations": ["location_id"],
    "pedestrian_readings": [
        "location_id",
        "sensed_at",
        "interval_minutes",
        "source",
    ],
    "historical_profiles": ["location_id", "day_of_week", "hour_of_day"],
    "refuges": ["refuge_id"],
}
LOAD_ORDER = [
    "sensor_locations",
    "pedestrian_readings",
    "historical_profiles",
    "refuges",
]

# SQLite allows a limited number of bind variables per statement (999 before
# 3.32, 32766 after). A single multi-row INSERT of a real extract exceeds that,
# so rows are sent in chunks sized to stay under the lower limit regardless of
# how many columns the dataset has.
SQLITE_MAX_BIND_VARIABLES = 900
POSTGRES_CHUNK_ROWS = 5000


def _chunk_size(dialect_name, column_count):
    if dialect_name == "sqlite":
        return max(1, SQLITE_MAX_BIND_VARIABLES // max(column_count, 1))
    return POSTGRES_CHUNK_ROWS


def upsert_rows(dataset, rows):
    """Upsert one already-validated dataset in the caller's transaction."""
    if not rows:
        raise ValueError("Refusing to load a dataset with zero rows")

    table = MODELS[dataset].__table__
    dialect_name = db.engine.dialect.name
    if dialect_name == "postgresql":
        insert_for_dialect = postgresql_insert
    elif dialect_name == "sqlite":
        insert_for_dialect = sqlite_insert
    else:
        raise RuntimeError(f"Unsupported database dialect: {dialect_name}")

    chunk_size = _chunk_size(dialect_name, len(rows[0]))
    for start in range(0, len(rows), chunk_size):
        statement = insert_for_dialect(table).values(rows[start : start + chunk_size])
        update_values = {
            column.name: getattr(statement.excluded, column.name)
            for column in table.columns
            if column.name not in CONFLICT_KEYS[dataset]
            and not (column.primary_key and column.autoincrement)
        }
        statement = statement.on_conflict_do_update(
            index_elements=CONFLICT_KEYS[dataset],
            set_=update_values,
        )
        db.session.execute(statement)


def load_datasets(files, dry_run=False, app=None):
    """Load selected datasets in dependency order and return per-dataset counts."""
    if dry_run:
        validated = {}
        known_sensor_ids = None
        for dataset in LOAD_ORDER:
            path = files.get(dataset)
            if not path:
                continue
            result = validate_dataset(dataset, path, known_sensor_ids)
            if result.skipped:
                raise ValueError(f"{path} is an example template and cannot be loaded")
            if not result.valid:
                detail = "; ".join(result.errors[:10])
                raise ValueError(f"{dataset} validation failed: {detail}")
            if result.row_count == 0:
                raise ValueError(f"{dataset} contains zero data rows")
            if dataset == "sensor_locations":
                known_sensor_ids = {row["location_id"] for row in result.rows}
            validated[dataset] = result.row_count
        return validated

    app = app or create_app()
    loaded = {}
    with app.app_context():
        known_sensor_ids = None
        if "sensor_locations" not in files:
            try:
                known_sensor_ids = set(
                    db.session.scalars(select(SensorLocation.location_id)).all()
                )
            except SQLAlchemyError:
                safe_rollback()
                raise RuntimeError("Could not verify sensor references") from None

        for dataset in LOAD_ORDER:
            path = files.get(dataset)
            if not path:
                continue
            result = validate_dataset(dataset, path, known_sensor_ids)
            if result.skipped:
                raise ValueError(f"{path} is an example template and cannot be loaded")
            if not result.valid:
                detail = "; ".join(result.errors[:10])
                raise ValueError(f"{dataset} validation failed: {detail}")
            if result.row_count == 0:
                raise ValueError(f"{dataset} contains zero data rows")

            if dataset == "sensor_locations":
                known_sensor_ids = {row["location_id"] for row in result.rows}
            try:
                db.session.rollback()
                with db.session.begin():
                    upsert_rows(dataset, result.rows)
                loaded[dataset] = result.row_count
            except (SQLAlchemyError, RuntimeError, ValueError):
                safe_rollback()
                raise RuntimeError(f"Database load failed for {dataset}") from None
    return loaded


def _parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Use all standard paths")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if any standard dataset file is missing",
    )
    for dataset in HEADERS:
        parser.add_argument(f"--{dataset.replace('_', '-')}", type=Path)
    return parser.parse_args()


def main():
    args = _parse_arguments()
    explicitly_selected = {
        dataset: getattr(args, dataset)
        for dataset in HEADERS
        if getattr(args, dataset) is not None
    }
    files = dict(DEFAULT_FILES) if args.all or not explicitly_selected else {}
    files.update(explicitly_selected)
    selected = {}
    missing = []
    for dataset, path in files.items():
        if path.name.endswith(".csv.example"):
            print(f"Refusing to load example template: {path}")
            return 1
        if path.exists():
            selected[dataset] = path
        else:
            missing.append((dataset, path))

    for dataset, path in missing:
        print(f"Skipped missing optional dataset: {dataset} ({path})")
    if missing and (args.strict or explicitly_selected):
        print("Missing selected data files are fatal in strict or explicit mode.")
        return 1
    if not selected:
        print("No loadable production data files were found; nothing was loaded.")
        return 1

    try:
        loaded = load_datasets(selected, dry_run=args.dry_run)
    except (RuntimeError, ValueError) as error:
        print(f"Load failed: {error}")
        return 1

    mode = "validated" if args.dry_run else "loaded"
    for dataset, count in loaded.items():
        print(f"{dataset}: {mode} {count} rows")
    if not loaded:
        print("No dataset rows were loaded.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
