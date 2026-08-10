"""Validate legacy CSV extracts without writing DS-managed Neon tables."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from scripts.validate_data import DEFAULT_FILES, HEADERS, validate_dataset


LOAD_ORDER = [
    "sensor_locations",
    "pedestrian_readings",
    "historical_profiles",
    "refuges",
]


def load_datasets(files, dry_run=False, app=None):
    """Validate selected files; direct database loading is intentionally disabled."""
    if not dry_run:
        raise RuntimeError(
            "Direct data loading is disabled. The citysense schema is managed by "
            "the DS team and must not be written by this application."
        )

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
        print("No loadable production data files were found; nothing was validated.")
        return 1

    try:
        validated = load_datasets(selected, dry_run=args.dry_run)
    except (RuntimeError, ValueError) as error:
        print(f"Validation failed: {error}")
        return 1

    for dataset, count in validated.items():
        print(f"{dataset}: validated {count} rows")
    return 0 if validated else 1


if __name__ == "__main__":
    raise SystemExit(main())
