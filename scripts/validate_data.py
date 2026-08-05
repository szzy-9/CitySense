"""Validate CitySense CSV handoff files without changing the database."""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_FILES = {
    "sensor_locations": ROOT_DIR / "data" / "processed" / "sensor_locations.csv",
    "pedestrian_readings": ROOT_DIR / "data" / "processed" / "pedestrian_readings.csv",
    "historical_profiles": (
        ROOT_DIR / "data" / "processed" / "sensor_historical_profiles.csv"
    ),
    "refuges": ROOT_DIR / "data" / "processed" / "refuges.csv",
}

HEADERS = {
    "sensor_locations": [
        "location_id",
        "sensor_name",
        "latitude",
        "longitude",
        "location_type",
        "status",
        "data_source",
        "updated_at",
    ],
    "pedestrian_readings": [
        "location_id",
        "sensed_at",
        "direction_1",
        "direction_2",
        "total_count",
        "interval_minutes",
        "source",
        "fetched_at",
    ],
    "historical_profiles": [
        "location_id",
        "day_of_week",
        "hour_of_day",
        "mean_count",
        "median_count",
        "percentile_80",
        "std_dev",
        "sample_count",
        "generated_at",
        "source_period_start",
        "source_period_end",
        "data_version",
    ],
    "refuges": [
        "refuge_id",
        "name",
        "latitude",
        "longitude",
        "refuge_type",
        "indoor_outdoor",
        "has_seating",
        "is_shaded",
        "lighting_level",
        "opening_hours",
        "short_description",
        "verified",
        "data_source",
        "last_checked_at",
    ],
}

UNIQUE_KEYS = {
    "sensor_locations": ("location_id",),
    "pedestrian_readings": (
        "location_id",
        "sensed_at",
        "interval_minutes",
        "source",
    ),
    "historical_profiles": ("location_id", "day_of_week", "hour_of_day"),
    "refuges": ("refuge_id",),
}


@dataclass
class ValidationResult:
    dataset: str
    path: Path
    rows: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped: bool = False

    @property
    def valid(self):
        return not self.errors

    @property
    def row_count(self):
        return len(self.rows)


def validate_dataset(dataset, path, known_sensor_ids=None, allow_example=False):
    """Validate one CSV and return typed rows plus row-level diagnostics."""
    file_path = Path(path)
    result = ValidationResult(dataset=dataset, path=file_path)
    if dataset not in HEADERS:
        result.errors.append(f"Unknown dataset: {dataset}")
        return result
    if file_path.name.endswith(".csv.example") and not allow_example:
        result.skipped = True
        result.warnings.append("Example template ignored; it is not loadable data.")
        return result
    if not file_path.exists():
        result.errors.append(f"File not found: {file_path}")
        return result
    if file_path.stat().st_size == 0:
        result.errors.append("File is empty and has no CSV header.")
        return result

    try:
        with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            actual_headers = reader.fieldnames or []
            if actual_headers != HEADERS[dataset]:
                result.errors.append(
                    "Header mismatch. Expected: "
                    + ",".join(HEADERS[dataset])
                    + "; received: "
                    + ",".join(actual_headers)
                )
                return result

            seen = set()
            parser = PARSERS[dataset]
            for row_number, raw_row in enumerate(reader, start=2):
                row_errors = []
                if None in raw_row:
                    row_errors.append("row contains more fields than the header")
                parsed = parser(raw_row, row_errors)
                key = tuple(parsed.get(field) for field in UNIQUE_KEYS[dataset])
                if key in seen:
                    row_errors.append(
                        "duplicate key "
                        + "/".join(str(value) for value in key)
                    )
                seen.add(key)

                if dataset in {"pedestrian_readings", "historical_profiles"}:
                    location_id = parsed.get("location_id")
                    if known_sensor_ids is not None and location_id not in known_sensor_ids:
                        row_errors.append(
                            f"location_id {location_id!r} is not present in sensor locations"
                        )

                if row_errors:
                    result.errors.extend(
                        f"Row {row_number}: {message}" for message in row_errors
                    )
                else:
                    result.rows.append(parsed)
    except (OSError, UnicodeError, csv.Error) as error:
        result.errors.append(f"Could not read CSV safely: {type(error).__name__}")

    if result.valid and result.row_count == 0:
        result.warnings.append("CSV has a valid header but contains zero data rows.")
    return result


def validate_files(files, allow_examples=False):
    """Validate a dataset-to-path mapping with cross-file sensor references."""
    results = {}
    sensor_ids = None
    if "sensor_locations" in files:
        sensor_result = validate_dataset(
            "sensor_locations",
            files["sensor_locations"],
            allow_example=allow_examples,
        )
        results["sensor_locations"] = sensor_result
        if sensor_result.valid and not sensor_result.skipped:
            sensor_ids = {row["location_id"] for row in sensor_result.rows}

    for dataset, path in files.items():
        if dataset == "sensor_locations":
            continue
        results[dataset] = validate_dataset(
            dataset,
            path,
            sensor_ids,
            allow_example=allow_examples,
        )
    return results


def _parse_sensor(row, errors):
    parsed = {
        "location_id": _required(row, "location_id", errors, 80),
        "sensor_name": _required(row, "sensor_name", errors, 200),
        "latitude": _float(row, "latitude", errors, -90, 90),
        "longitude": _float(row, "longitude", errors, -180, 180),
        "location_type": _optional_text(row, "location_type", errors, 80),
        "status": _optional_text(row, "status", errors, 30),
        "data_source": _optional_text(row, "data_source", errors, 80),
        "updated_at": _datetime(row, "updated_at", errors, required=False),
    }
    return parsed


def _parse_reading(row, errors):
    return {
        "location_id": _required(row, "location_id", errors, 80),
        "sensed_at": _datetime(row, "sensed_at", errors),
        "direction_1": _integer(
            row, "direction_1", errors, minimum=0, required=False
        ),
        "direction_2": _integer(
            row, "direction_2", errors, minimum=0, required=False
        ),
        "total_count": _integer(row, "total_count", errors, minimum=0),
        "interval_minutes": _integer(
            row, "interval_minutes", errors, minimum=1
        ),
        "source": _required(row, "source", errors, 80),
        "fetched_at": _datetime(row, "fetched_at", errors),
    }


def _parse_profile(row, errors):
    parsed = {
        "location_id": _required(row, "location_id", errors, 80),
        "day_of_week": _integer(row, "day_of_week", errors, 0, 6),
        "hour_of_day": _integer(row, "hour_of_day", errors, 0, 23),
        "mean_count": _float(row, "mean_count", errors, minimum=0),
        "median_count": _float(row, "median_count", errors, minimum=0),
        "percentile_80": _float(row, "percentile_80", errors, minimum=0),
        "std_dev": _float(row, "std_dev", errors, minimum=0),
        "sample_count": _integer(row, "sample_count", errors, minimum=0),
        "generated_at": _datetime(row, "generated_at", errors),
        "source_period_start": _date(row, "source_period_start", errors),
        "source_period_end": _date(row, "source_period_end", errors),
        "data_version": _required(row, "data_version", errors, 40),
    }
    if (
        parsed["source_period_start"]
        and parsed["source_period_end"]
        and parsed["source_period_end"] < parsed["source_period_start"]
    ):
        errors.append("source_period_end must not be earlier than source_period_start")
    return parsed


def _parse_refuge(row, errors):
    parsed = {
        "refuge_id": _required(row, "refuge_id", errors, 80),
        "name": _required(row, "name", errors, 160),
        "latitude": _float(row, "latitude", errors, -90, 90),
        "longitude": _float(row, "longitude", errors, -180, 180),
        "refuge_type": _required(row, "refuge_type", errors, 80),
        "indoor_outdoor": _optional_text(row, "indoor_outdoor", errors, 40),
        "has_seating": _boolean(row, "has_seating", errors, required=False),
        "is_shaded": _boolean(row, "is_shaded", errors, required=False),
        "lighting_level": _optional_text(row, "lighting_level", errors, 80),
        "opening_hours": _optional_text(row, "opening_hours", errors, 200),
        "short_description": _required(row, "short_description", errors, 300),
        "verified": _boolean(
            row, "verified", errors, required=False, default=False
        ),
        "data_source": _optional_text(row, "data_source", errors, 80),
        "last_checked_at": _datetime(
            row, "last_checked_at", errors, required=False
        ),
    }
    return parsed


PARSERS: dict[str, Callable] = {
    "sensor_locations": _parse_sensor,
    "pedestrian_readings": _parse_reading,
    "historical_profiles": _parse_profile,
    "refuges": _parse_refuge,
}


def _required(row, field, errors, maximum_length=None):
    value = (row.get(field) or "").strip()
    if not value:
        errors.append(f"{field} is required")
        return None
    if maximum_length and len(value) > maximum_length:
        errors.append(f"{field} exceeds {maximum_length} characters")
    return value


def _optional_text(row, field, errors, maximum_length=None):
    value = (row.get(field) or "").strip()
    if not value:
        return None
    if maximum_length and len(value) > maximum_length:
        errors.append(f"{field} exceeds {maximum_length} characters")
    return value


def _integer(row, field, errors, minimum=None, maximum=None, required=True):
    value = (row.get(field) or "").strip()
    if not value and not required:
        return None
    try:
        parsed = int(value)
    except ValueError:
        errors.append(f"{field} must be an integer")
        return None
    if minimum is not None and parsed < minimum:
        errors.append(f"{field} must be at least {minimum}")
    if maximum is not None and parsed > maximum:
        errors.append(f"{field} must be at most {maximum}")
    return parsed


def _float(row, field, errors, minimum=None, maximum=None):
    value = (row.get(field) or "").strip()
    try:
        parsed = float(value)
    except ValueError:
        errors.append(f"{field} must be numeric")
        return None
    if not math.isfinite(parsed):
        errors.append(f"{field} must be a finite number")
        return None
    if minimum is not None and parsed < minimum:
        errors.append(f"{field} must be at least {minimum}")
    if maximum is not None and parsed > maximum:
        errors.append(f"{field} must be at most {maximum}")
    return parsed


def _boolean(row, field, errors, required=True, default=None):
    value = (row.get(field) or "").strip().lower()
    if not value and not required:
        return default
    if value in {"true", "1", "yes", "y"}:
        return True
    if value in {"false", "0", "no", "n"}:
        return False
    errors.append(f"{field} must be true or false")
    return None


def _date(row, field, errors, required=True):
    value = (row.get(field) or "").strip()
    if not value and not required:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{field} must be an ISO date (YYYY-MM-DD)")
        return None


def _datetime(row, field, errors, required=True):
    value = (row.get(field) or "").strip()
    if not value and not required:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field} must be an ISO 8601 timestamp")
        return None
    if parsed.tzinfo is None:
        errors.append(f"{field} must include a timezone offset")
    return parsed


def _parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Validate standard paths")
    for dataset in HEADERS:
        parser.add_argument(f"--{dataset.replace('_', '-')}", type=Path)
    return parser.parse_args()


def main():
    args = _parse_arguments()
    files = {}
    if args.all:
        files.update(
            {
                dataset: path
                for dataset, path in DEFAULT_FILES.items()
                if path.exists() and not path.name.endswith(".csv.example")
            }
        )
    for dataset in HEADERS:
        value = getattr(args, dataset)
        if value:
            files[dataset] = value

    if not files:
        print("No production data files were found or selected.")
        return 0

    explicit_examples = any(
        path.name.endswith(".csv.example") for path in files.values()
    )
    results = validate_files(files, allow_examples=explicit_examples)
    has_errors = False
    for dataset, result in results.items():
        state = "SKIPPED" if result.skipped else "PASS" if result.valid else "FAIL"
        print(f"{dataset}: {state}; rows={result.row_count}; file={result.path}")
        for warning in result.warnings:
            print(f"  warning: {warning}")
        for error in result.errors:
            print(f"  error: {error}")
        has_errors = has_errors or not result.valid
    return 1 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
