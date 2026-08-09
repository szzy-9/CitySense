"""Derive contract-compliant CitySense CSV files from an hourly analysis extract.

The analysis extract (``data/processed/analysis_hourly.csv``) is a wide,
denormalised join of the City of Melbourne pedestrian counting system with
microclimate and canopy attributes. This script projects it onto the three
normalised handoff files the loader understands:

- ``sensor_locations.csv``            one row per sensor (3NF: coordinates split)
- ``pedestrian_readings.csv``         hourly counts, composite natural key
- ``sensor_historical_profiles.csv``  day-of-week/hour baselines for prediction

Nothing is invented. Sensors without usable coordinates are dropped, profile
cells are emitted only where real observations exist, and the reading window is
bounded so the handoff file stays within the documented contract.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from scripts.validate_data import HEADERS  # noqa: E402


DEFAULT_SOURCE = ROOT_DIR / "data" / "processed" / "analysis_hourly.csv"
OUTPUT_DIR = ROOT_DIR / "data" / "processed"

# The extract stores Melbourne local clock hours alongside a UTC-suffixed
# datetime column. Readings are anchored to Melbourne time and converted once,
# so downstream day_of_week/hour_of_day match the city the user is walking in.
MELBOURNE_UTC_OFFSET_HOURS = 10
SOURCE_NAME = "analysis_hourly"
INTERVAL_MINUTES = 60
MISSING = {"", "NA", "N/A", "null", "None"}

# Profile cells built from fewer observations than this are not published: a
# median over one or two Tuesdays is not a baseline, and the prediction layer
# would otherwise present it with unearned confidence.
MIN_PROFILE_SAMPLES = 4


def is_missing(value):
    return value is None or value.strip() in MISSING


def parse_reading_timestamp(row):
    """Return a timezone-aware UTC timestamp for one extract row."""
    sensing_date = (row.get("sensing_date") or "").strip()
    hour_text = (row.get("hour_day") or "").strip()
    if not sensing_date or not hour_text:
        return None
    try:
        day = date.fromisoformat(sensing_date)
        hour = int(hour_text)
    except ValueError:
        return None
    if not 0 <= hour <= 23:
        return None

    local = datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)
    return local - timedelta(hours=MELBOURNE_UTC_OFFSET_HOURS)


def read_extract(source_path, window_days):
    """Stream the extract once, collecting sensors, readings and profile samples."""
    sensors = {}
    readings = []
    samples = defaultdict(list)
    latest_day = None
    earliest_day = None
    skipped = defaultdict(int)

    with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = [
            column
            for column in ("location_id", "sensing_date", "hour_day", "total_of_directions")
            if column not in (reader.fieldnames or [])
        ]
        if missing_columns:
            raise ValueError(
                "Extract is missing required columns: " + ", ".join(missing_columns)
            )

        for row in reader:
            location_id = (row.get("location_id") or "").strip()
            if not location_id:
                skipped["no_location_id"] += 1
                continue

            latitude = (row.get("ped_lat") or "").strip()
            longitude = (row.get("ped_lon") or "").strip()
            if is_missing(latitude) or is_missing(longitude):
                skipped["no_coordinates"] += 1
                continue

            sensed_at = parse_reading_timestamp(row)
            if sensed_at is None:
                skipped["bad_timestamp"] += 1
                continue

            total_text = (row.get("total_of_directions") or "").strip()
            if is_missing(total_text):
                skipped["no_count"] += 1
                continue
            try:
                total_count = int(float(total_text))
            except ValueError:
                skipped["bad_count"] += 1
                continue
            if total_count < 0:
                skipped["negative_count"] += 1
                continue

            if location_id not in sensors:
                sensors[location_id] = {
                    "location_id": location_id,
                    # sensor_name is the device code (Swa295_T); the
                    # description is the place a person would recognise
                    # (Melbourne Central). The code was reaching the screen as
                    # "Busiest near Swa148_T".
                    "sensor_name": (
                        (row.get("sensor_description") or "").strip()
                        or (row.get("sensor_name") or "").strip()
                        or location_id
                    ),
                    "latitude": latitude,
                    "longitude": longitude,
                }

            sensing_day = date.fromisoformat(row["sensing_date"].strip())
            if latest_day is None or sensing_day > latest_day:
                latest_day = sensing_day
            if earliest_day is None or sensing_day < earliest_day:
                earliest_day = sensing_day

            # Profiles use the whole history; readings are trimmed later once the
            # extract's last day is known.
            local_time = sensed_at + timedelta(hours=MELBOURNE_UTC_OFFSET_HOURS)
            samples[(location_id, local_time.weekday(), local_time.hour)].append(
                total_count
            )
            readings.append(
                {
                    "location_id": location_id,
                    "sensed_at": sensed_at,
                    "sensing_day": sensing_day,
                    "direction_1": _optional_int(row.get("direction_1")),
                    "direction_2": _optional_int(row.get("direction_2")),
                    "total_count": total_count,
                }
            )

    if latest_day is None:
        raise ValueError("Extract contained no usable rows")

    cutoff = latest_day - timedelta(days=window_days - 1)
    windowed = [reading for reading in readings if reading["sensing_day"] >= cutoff]
    return sensors, windowed, samples, earliest_day, latest_day, cutoff, skipped


def _optional_int(value):
    if is_missing(value):
        return None
    try:
        return max(0, int(float(value.strip())))
    except ValueError:
        return None


def build_profiles(samples, period_start, period_end, generated_at, data_version):
    """Aggregate per-sensor day/hour baselines from the collected observations."""
    rows = []
    for (location_id, day_of_week, hour_of_day), counts in sorted(samples.items()):
        if len(counts) < MIN_PROFILE_SAMPLES:
            continue
        rows.append(
            {
                "location_id": location_id,
                "day_of_week": day_of_week,
                "hour_of_day": hour_of_day,
                "mean_count": round(statistics.fmean(counts), 2),
                "median_count": round(statistics.median(counts), 2),
                "percentile_80": round(_percentile(counts, 0.8), 2),
                "std_dev": round(
                    statistics.pstdev(counts) if len(counts) > 1 else 0.0, 2
                ),
                "sample_count": len(counts),
                "generated_at": generated_at,
                "source_period_start": period_start.isoformat(),
                "source_period_end": period_end.isoformat(),
                "data_version": data_version,
            }
        )
    return rows


def _percentile(values, fraction):
    """Linear-interpolation percentile, matching numpy's default method."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def write_csv(path, dataset, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS[dataset])
        writer.writeheader()
        writer.writerows(rows)


def build(source_path, output_dir, window_days, data_version):
    sensors, readings, samples, earliest_day, latest_day, cutoff, skipped = read_extract(
        source_path, window_days
    )
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    sensor_rows = [
        {
            "location_id": sensor["location_id"],
            "sensor_name": sensor["sensor_name"],
            "latitude": sensor["latitude"],
            "longitude": sensor["longitude"],
            "location_type": "pedestrian_counter",
            "status": "active",
            "data_source": SOURCE_NAME,
            "updated_at": generated_at,
        }
        for sensor in sorted(sensors.values(), key=lambda item: item["location_id"])
    ]

    reading_rows = [
        {
            "location_id": reading["location_id"],
            "sensed_at": reading["sensed_at"].isoformat().replace("+00:00", "Z"),
            "direction_1": "" if reading["direction_1"] is None else reading["direction_1"],
            "direction_2": "" if reading["direction_2"] is None else reading["direction_2"],
            "total_count": reading["total_count"],
            "interval_minutes": INTERVAL_MINUTES,
            "source": SOURCE_NAME,
            "fetched_at": generated_at,
        }
        for reading in sorted(
            readings, key=lambda item: (item["location_id"], item["sensed_at"])
        )
    ]

    profile_rows = build_profiles(
        samples,
        period_start=earliest_day,
        period_end=latest_day,
        generated_at=generated_at,
        data_version=data_version,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "sensor_locations.csv", "sensor_locations", sensor_rows)
    write_csv(output_dir / "pedestrian_readings.csv", "pedestrian_readings", reading_rows)
    write_csv(
        output_dir / "sensor_historical_profiles.csv",
        "historical_profiles",
        profile_rows,
    )

    return {
        "sensors": len(sensor_rows),
        "readings": len(reading_rows),
        "profiles": len(profile_rows),
        "reading_window": f"{cutoff.isoformat()} to {latest_day.isoformat()}",
        "profile_period": f"{earliest_day.isoformat()} to {latest_day.isoformat()}",
        "skipped": dict(skipped),
    }


def _parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument(
        "--window-days",
        type=int,
        default=28,
        help="Trailing days of hourly readings to publish (default: 28)",
    )
    parser.add_argument(
        "--data-version",
        default=f"analysis-hourly-{date.today().isoformat()}",
    )
    return parser.parse_args()


def main():
    args = _parse_arguments()
    if not args.source.exists():
        print(f"Source extract not found: {args.source}")
        return 1
    if args.window_days < 1:
        print("--window-days must be at least 1")
        return 1

    try:
        summary = build(args.source, args.output_dir, args.window_days, args.data_version)
    except (OSError, ValueError, csv.Error) as error:
        print(f"Build failed: {error}")
        return 1

    print(f"sensor_locations: {summary['sensors']} rows")
    print(f"pedestrian_readings: {summary['readings']} rows ({summary['reading_window']})")
    print(f"sensor_historical_profiles: {summary['profiles']} rows ({summary['profile_period']})")
    if summary["skipped"]:
        print("skipped source rows: " + ", ".join(
            f"{reason}={count}" for reason, count in sorted(summary["skipped"].items())
        ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
