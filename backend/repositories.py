"""Database access for CitySense-owned and DS-managed data.

The DS tables are reflected from the existing ``citysense`` schema and are
read only. Functions return plain dictionaries so database rows never cross
the API boundary. Database errors are rolled back and converted to safe empty
results.
"""

from collections import defaultdict
from weakref import WeakKeyDictionary

from sqlalchemy import MetaData, Table, cast, func, or_, select, String
from sqlalchemy.exc import SQLAlchemyError

from backend.database import safe_rollback
from backend.models import db


DATA_SCHEMA = "citysense"
DATA_TABLES = {
    "sensor_locations": "sensor_location",
    "historical_profiles": "sensor_load_profile",
    "sensor_thresholds": "sensor_threshold",
    "refuges": "refuge",
    "refuge_opening_hours": "refuge_opening_hours",
}
LOAD_BANDS = {"LOW", "MODERATE", "HIGH"}
CONFIDENCE_LEVELS = {"LOW", "MEDIUM", "HIGH"}
_TABLE_CACHE = WeakKeyDictionary()


def list_active_sensor_locations():
    """Return CBD sensors without interpreting the DS ``status`` code."""
    try:
        table = _external_table("sensor_location")
        rows = db.session.execute(
            select(table)
            .where(table.c.in_cbd.is_(True))
            .order_by(table.c.location_id)
        ).mappings().all()
        return [_sensor_location_dict(row) for row in rows]
    except (SQLAlchemyError, KeyError, TypeError, ValueError):
        safe_rollback()
        return []


def get_sensor_locations_by_ids(location_ids):
    identifiers = sorted({str(value) for value in location_ids if value})
    if not identifiers:
        return []
    try:
        table = _external_table("sensor_location")
        rows = db.session.execute(
            select(table).where(cast(table.c.location_id, String).in_(identifiers))
        ).mappings().all()
        return [_sensor_location_dict(row) for row in rows]
    except (SQLAlchemyError, KeyError, TypeError, ValueError):
        safe_rollback()
        return []


def get_historical_profiles(location_ids, target_datetime):
    profiles = get_historical_profiles_for_times(location_ids, [target_datetime])
    return {
        location_id: profile
        for (location_id, _day, _hour), profile in profiles.items()
    }


def get_historical_profiles_for_times(location_ids, target_datetimes):
    identifiers = sorted({str(value) for value in location_ids if value})
    time_keys = sorted(
        {(value.weekday(), value.hour) for value in target_datetimes if value}
    )
    if not identifiers or not time_keys:
        return {}

    try:
        table = _external_table("sensor_load_profile")
        time_filter = or_(
            *[
                (table.c.dow == day_value)
                & (table.c.hour_of_day == hour_value)
                for day_value, hour_value in time_keys
            ]
        )
        rows = db.session.execute(
            select(table).where(
                cast(table.c.location_id, String).in_(identifiers),
                time_filter,
            )
        ).mappings().all()
        profiles = [_profile_dict(row) for row in rows]
        return {
            (
                profile["location_id"],
                profile["day_of_week"],
                profile["hour_of_day"],
            ): profile
            for profile in profiles
        }
    except (SQLAlchemyError, KeyError, TypeError, ValueError):
        safe_rollback()
        return {}


def get_sensor_thresholds(location_ids):
    """Return optional DS threshold metadata without reclassifying profiles."""
    identifiers = sorted({str(value) for value in location_ids if value})
    if not identifiers:
        return {}
    try:
        table = _external_table("sensor_threshold")
        rows = db.session.execute(
            select(table).where(cast(table.c.location_id, String).in_(identifiers))
        ).mappings().all()
        return {
            str(row["location_id"]): {
                "p50": _float_or_none(row["p50"]),
                "p80": _float_or_none(row["p80"]),
                "first_seen": _iso_value(row["first_seen"]),
                "last_seen": _iso_value(row["last_seen"]),
                "completeness": _float_or_none(row["completeness"]),
            }
            for row in rows
        }
    except (SQLAlchemyError, KeyError, TypeError, ValueError):
        safe_rollback()
        return {}


def list_database_refuges():
    try:
        refuge_table = _external_table("refuge")
        landmark_table = _external_table("landmark")
        category_table = _external_table("landmark_category")
        refuge_with_category = refuge_table.outerjoin(
            landmark_table,
            refuge_table.c.landmark_id == landmark_table.c.landmark_id,
        ).outerjoin(
            category_table,
            landmark_table.c.category_id == category_table.c.category_id,
        )
        rows = db.session.execute(
            select(
                refuge_table,
                category_table.c.sub_theme.label("_refuge_type"),
            )
            .select_from(refuge_with_category)
            .order_by(refuge_table.c.refuge_name)
        ).mappings().all()
    except (SQLAlchemyError, KeyError, TypeError, ValueError):
        safe_rollback()
        return []

    opening_hours = _opening_hours_by_refuge()
    refuges = []
    for row in rows:
        try:
            refuge = _refuge_dict(row, opening_hours)
        except (KeyError, TypeError, ValueError):
            continue
        refuges.append(refuge)
    return refuges


def list_refuges():
    """Repository-level refuge listing retained as the public data-access name."""
    return list_database_refuges()


def data_table_counts():
    counts = {
        name: _external_table_count(table_name)
        for name, table_name in DATA_TABLES.items()
    }
    # Live pedestrian readings remain an in-memory City of Melbourne API feed.
    # Keep the existing status key without implying that a database table exists.
    counts["pedestrian_readings"] = None
    return counts


def database_has_sensor_locations():
    return _external_table_has_rows("sensor_location")


def database_has_historical_profiles():
    return _external_table_has_rows("sensor_load_profile")


def database_has_refuges():
    return _external_table_has_rows("refuge")


def normalize_load_band(value):
    normalized = str(value or "").strip().upper()
    return normalized if normalized in LOAD_BANDS else "NO_DATA"


def normalize_confidence(value):
    normalized = str(value or "").strip().upper()
    return normalized if normalized in CONFIDENCE_LEVELS else "LOW"


def _external_table(table_name):
    engine = db.engine
    engine_tables = _TABLE_CACHE.setdefault(engine, {})
    if table_name not in engine_tables:
        engine_tables[table_name] = Table(
            table_name,
            MetaData(),
            schema=DATA_SCHEMA,
            autoload_with=engine,
            resolve_fks=False,
        )
    return engine_tables[table_name]


def _external_table_count(table_name):
    try:
        table = _external_table(table_name)
        return db.session.execute(select(func.count()).select_from(table)).scalar_one()
    except (SQLAlchemyError, KeyError, TypeError, ValueError):
        safe_rollback()
        return None


def _external_table_has_rows(table_name):
    try:
        table = _external_table(table_name)
        first_column = next(iter(table.c))
        return db.session.execute(select(first_column).limit(1)).first() is not None
    except (SQLAlchemyError, KeyError, TypeError, ValueError, StopIteration):
        safe_rollback()
        return False


def _sensor_location_dict(row):
    return {
        "location_id": str(row["location_id"]),
        "sensor_name": str(row["sensor_name"]),
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
        "location_type": row["location_type"],
        "status": row["status"],
        "data_source": "NEON",
        "updated_at": None,
    }


def _profile_dict(row):
    return {
        "location_id": str(row["location_id"]),
        "day_of_week": int(row["dow"]),
        "hour_of_day": int(row["hour_of_day"]),
        "median_count": _float_or_none(row["median_count"]),
        "median_per_min": _float_or_none(row["median_per_min"]),
        "mean_count": _float_or_none(row["mean_count"]),
        "mean_per_min": _float_or_none(row["mean_per_min"]),
        "std_dev": _float_or_none(row["std_dev"]),
        "sample_count": int(row["n_obs"]),
        "load_band": normalize_load_band(row["load_band"]),
        "confidence": normalize_confidence(row["confidence"]),
        "data_version": row["band_version"],
    }


def _opening_hours_by_refuge():
    try:
        table = _external_table("refuge_opening_hours")
        rows = db.session.execute(
            select(table).order_by(
                table.c.refuge_id,
                table.c.dow,
                table.c.opens_at,
            )
        ).mappings().all()
    except (SQLAlchemyError, KeyError, TypeError, ValueError):
        safe_rollback()
        return {}

    grouped = defaultdict(list)
    for row in rows:
        grouped[str(row["refuge_id"])].append(row)
    return {
        identifier: _format_opening_hours(hours)
        for identifier, hours in grouped.items()
    }


def _format_opening_hours(rows):
    day_labels = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    intervals_by_day = defaultdict(list)
    for row in rows:
        day = int(row["dow"])
        if day not in range(7):
            continue
        intervals_by_day[day].append(
            f"{_format_time(row['opens_at'])}-{_format_time(row['closes_at'])}"
        )

    descriptions = [
        f"{day_labels[day]} {', '.join(intervals_by_day[day])}"
        for day in sorted(intervals_by_day)
    ]
    return "; ".join(descriptions) if descriptions else None


def _refuge_dict(row, opening_hours):
    identifier = str(row["refuge_id"])
    availability = opening_hours.get(identifier)
    return {
        "id": identifier,
        "name": str(row["refuge_name"]),
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
        "refuge_type": str(row["_refuge_type"] or "Uncategorised"),
        "indoor_outdoor": row["indoor_outdoor"],
        "has_seating": bool(row["has_seating"]),
        "is_shaded": None,
        "lighting_level": row["lighting_level"],
        "step_free": row["step_free"],
        "short_description": str(row["source_note"] or ""),
        "opening_hours": availability,
        "availability": availability,
        "verified": True,
        "data_source": "NEON",
        "last_checked_at": _iso_value(row["verified_on"]),
    }


def _iso_value(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _float_or_none(value):
    return float(value) if value is not None else None


def _format_time(value):
    if value is None:
        return "unknown"
    return value.strftime("%H:%M") if hasattr(value, "strftime") else str(value)[:5]
