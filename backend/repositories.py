"""Database access for CitySense-owned and DS-managed data.

The DS tables are reflected from the existing ``citysense`` schema and are
read only. Only ``route_searches`` is owned and written by this backend.
Functions return plain dictionaries so database rows never cross the API
boundary. Database errors are rolled back and converted to safe empty results.
"""

from collections import defaultdict
from weakref import WeakKeyDictionary

from sqlalchemy import MetaData, Table, cast, func, or_, select, String
from sqlalchemy.exc import SQLAlchemyError

from backend.database import safe_rollback
from backend.models import RouteSearch, db


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
    try:
        table = _external_table("sensor_location")
        identifier = _required_column(table, "location_id", "sensor_id", "id")
        statement = select(table)

        status = _optional_column(table, "status", "sensor_status")
        is_active = _optional_column(table, "is_active", "active")
        if status is not None:
            statement = statement.where(
                or_(
                    status.is_(None),
                    func.lower(cast(status, String)).in_(
                        ("active", "enabled", "operational")
                    ),
                )
            )
        elif is_active is not None:
            statement = statement.where(is_active.is_(True))

        rows = db.session.execute(statement.order_by(identifier)).mappings().all()
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
        identifier = _required_column(table, "location_id", "sensor_id", "id")
        rows = db.session.execute(
            select(table).where(cast(identifier, String).in_(identifiers))
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
        identifier = _required_column(table, "location_id", "sensor_id")
        day = _required_column(table, "dow")
        hour = _required_column(table, "hour_of_day")
        time_filter = or_(
            *[
                (day == day_value) & (hour == hour_value)
                for day_value, hour_value in time_keys
            ]
        )
        rows = db.session.execute(
            select(table).where(
                cast(identifier, String).in_(identifiers),
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
        identifier = _required_column(table, "location_id", "sensor_id")
        rows = db.session.execute(
            select(table).where(cast(identifier, String).in_(identifiers))
        ).mappings().all()
        return {
            str(_required_value(row, "location_id", "sensor_id")): {
                "p50": _value(row, "p50"),
                "p80": _value(row, "p80"),
                "data_version": _value(
                    row,
                    "band_version",
                    "data_version",
                    "threshold_version",
                ),
            }
            for row in rows
        }
    except (SQLAlchemyError, KeyError, TypeError, ValueError):
        safe_rollback()
        return {}


def list_database_refuges():
    try:
        table = _external_table("refuge")
        name = _required_column(table, "name", "refuge_name")
        rows = db.session.execute(select(table).order_by(name)).mappings().all()
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


def record_route_search(metadata):
    search = RouteSearch(**metadata)
    try:
        db.session.add(search)
        db.session.commit()
        return True
    except SQLAlchemyError:
        safe_rollback()
        return False


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
        "location_id": str(_required_value(row, "location_id", "sensor_id", "id")),
        "sensor_name": str(
            _value(
                row,
                "sensor_name",
                "sensor_description",
                "name",
                default="Pedestrian sensor",
            )
        ),
        "latitude": float(_required_value(row, "latitude", "lat")),
        "longitude": float(_required_value(row, "longitude", "lon", "lng")),
        "location_type": _value(row, "location_type", "sensor_type"),
        "status": _value(row, "status", "sensor_status"),
        "data_source": _value(row, "data_source", "source", default="NEON"),
        "updated_at": _iso_value(
            _value(row, "updated_at", "last_updated", "last_checked_at")
        ),
    }


def _profile_dict(row):
    return {
        "location_id": str(_required_value(row, "location_id", "sensor_id")),
        "day_of_week": int(_required_value(row, "dow")),
        "hour_of_day": int(_required_value(row, "hour_of_day")),
        "median_count": _value(row, "median_count"),
        "median_per_min": _value(row, "median_per_min"),
        "mean_count": _value(row, "mean_count"),
        "mean_per_min": _value(row, "mean_per_min"),
        "std_dev": _value(row, "std_dev"),
        "sample_count": int(_value(row, "n_obs", default=0) or 0),
        "load_band": normalize_load_band(_value(row, "load_band")),
        "confidence": normalize_confidence(_value(row, "confidence")),
        "data_version": _value(row, "band_version"),
    }


def _opening_hours_by_refuge():
    try:
        table = _external_table("refuge_opening_hours")
        rows = db.session.execute(select(table)).mappings().all()
    except (SQLAlchemyError, KeyError, TypeError, ValueError):
        safe_rollback()
        return {}

    grouped = defaultdict(list)
    for row in rows:
        identifier = _value(row, "refuge_id", "id")
        if identifier is not None:
            grouped[str(identifier)].append(row)
    return {
        identifier: _format_opening_hours(hours)
        for identifier, hours in grouped.items()
    }


def _format_opening_hours(rows):
    descriptions = []
    for row in rows:
        direct = _value(row, "opening_hours", "hours", "availability")
        if direct:
            descriptions.append(str(direct))
            continue

        day = _value(row, "day_name", "weekday", "day_of_week", "dow")
        day_label = str(day) if day is not None else "Daily"
        if _as_boolean(_value(row, "is_closed", "closed")):
            descriptions.append(f"{day_label}: closed")
            continue
        if _as_boolean(_value(row, "is_24_hours", "open_24_hours")):
            descriptions.append(f"{day_label}: open 24 hours")
            continue

        opens = _value(row, "opens_at", "open_time", "opening_time")
        closes = _value(row, "closes_at", "close_time", "closing_time")
        if opens is not None or closes is not None:
            descriptions.append(
                f"{day_label}: {opens or 'unknown'}-{closes or 'unknown'}"
            )

    return "; ".join(descriptions) if descriptions else None


def _refuge_dict(row, opening_hours):
    identifier = str(_required_value(row, "refuge_id", "id"))
    availability = opening_hours.get(identifier) or _value(
        row,
        "opening_hours",
        "availability",
    )
    return {
        "id": identifier,
        "name": str(_required_value(row, "name", "refuge_name")),
        "latitude": float(_required_value(row, "latitude", "lat")),
        "longitude": float(_required_value(row, "longitude", "lon", "lng")),
        "refuge_type": str(
            _value(row, "refuge_type", "type", "category", default="Quiet place")
        ),
        "indoor_outdoor": _value(row, "indoor_outdoor", "setting"),
        "has_seating": _as_boolean(_value(row, "has_seating", "seating")),
        "is_shaded": _as_boolean(_value(row, "is_shaded", "shaded")),
        "lighting_level": _value(row, "lighting_level"),
        "short_description": str(
            _value(
                row,
                "short_description",
                "description",
                default="Check local conditions before travelling.",
            )
        ),
        "opening_hours": availability,
        "availability": availability,
        "verified": _as_boolean(_value(row, "verified")),
        "data_source": _value(row, "data_source", "source", default="NEON"),
        "last_checked_at": _iso_value(
            _value(row, "last_checked_at", "updated_at")
        ),
    }


def _required_column(table, *names):
    column = _optional_column(table, *names)
    if column is None:
        raise KeyError(f"Required column is missing from {table.fullname}")
    return column


def _optional_column(table, *names):
    for name in names:
        if name in table.c:
            return table.c[name]
    return None


def _required_value(row, *names):
    value = _value(row, *names)
    if value is None:
        raise KeyError("Required database value is missing")
    return value


def _value(row, *names, default=None):
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return default


def _iso_value(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _as_boolean(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}
