"""Small database access layer used by API and service code.

Functions return plain dictionaries so SQLAlchemy objects never cross the API
boundary. Database errors are rolled back and converted to safe empty results.
"""

from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError

from backend.database import safe_rollback
from backend.models import (
    PedestrianReading,
    Refuge,
    RouteSearch,
    SensorHistoricalProfile,
    SensorLocation,
    db,
)


def list_active_sensor_locations():
    try:
        rows = (
            SensorLocation.query.filter(
                or_(
                    SensorLocation.status.is_(None),
                    SensorLocation.status.ilike("active"),
                )
            )
            .order_by(SensorLocation.location_id)
            .all()
        )
        return [_sensor_location_dict(row) for row in rows]
    except SQLAlchemyError:
        safe_rollback()
        return []


def get_sensor_locations_by_ids(location_ids):
    identifiers = sorted({str(value) for value in location_ids if value})
    if not identifiers:
        return []
    try:
        rows = SensorLocation.query.filter(
            SensorLocation.location_id.in_(identifiers)
        ).all()
        return [_sensor_location_dict(row) for row in rows]
    except SQLAlchemyError:
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

    time_filters = [
        and_(
            SensorHistoricalProfile.day_of_week == day,
            SensorHistoricalProfile.hour_of_day == hour,
        )
        for day, hour in time_keys
    ]
    try:
        rows = SensorHistoricalProfile.query.filter(
            SensorHistoricalProfile.location_id.in_(identifiers),
            or_(*time_filters),
        ).all()
        return {
            (row.location_id, row.day_of_week, row.hour_of_day): _profile_dict(row)
            for row in rows
        }
    except SQLAlchemyError:
        safe_rollback()
        return {}


def list_database_refuges():
    try:
        rows = Refuge.query.order_by(Refuge.name).all()
        return [_refuge_dict(row) for row in rows]
    except SQLAlchemyError:
        safe_rollback()
        return []


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
    models = {
        "sensor_locations": SensorLocation,
        "pedestrian_readings": PedestrianReading,
        "historical_profiles": SensorHistoricalProfile,
        "refuges": Refuge,
    }
    try:
        return {name: model.query.count() for name, model in models.items()}
    except SQLAlchemyError:
        safe_rollback()
        return {name: None for name in models}


def database_has_sensor_locations():
    return _has_rows(SensorLocation)


def database_has_historical_profiles():
    return _has_rows(SensorHistoricalProfile)


def database_has_refuges():
    return _has_rows(Refuge)


def _has_rows(model):
    try:
        return db.session.query(model).first() is not None
    except SQLAlchemyError:
        safe_rollback()
        return False


def _sensor_location_dict(row):
    return {
        "location_id": row.location_id,
        "sensor_name": row.sensor_name,
        "latitude": row.latitude,
        "longitude": row.longitude,
        "location_type": row.location_type,
        "status": row.status,
        "data_source": row.data_source,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _profile_dict(row):
    return {
        "location_id": row.location_id,
        "day_of_week": row.day_of_week,
        "hour_of_day": row.hour_of_day,
        "mean_count": row.mean_count,
        "median_count": row.median_count,
        "percentile_80": row.percentile_80,
        "std_dev": row.std_dev,
        "sample_count": row.sample_count,
        "source_period_start": row.source_period_start.isoformat(),
        "source_period_end": row.source_period_end.isoformat(),
        "generated_at": row.generated_at.isoformat(),
        "data_version": row.data_version,
    }


def _refuge_dict(row):
    return {
        "id": row.refuge_id,
        "name": row.name,
        "latitude": row.latitude,
        "longitude": row.longitude,
        "refuge_type": row.refuge_type,
        "indoor_outdoor": row.indoor_outdoor,
        "has_seating": row.has_seating,
        "is_shaded": row.is_shaded,
        "lighting_level": row.lighting_level,
        "short_description": row.short_description,
        "opening_hours": row.opening_hours,
        "availability": row.opening_hours,
        "verified": row.verified,
        "data_source": row.data_source,
        "last_checked_at": (
            row.last_checked_at.isoformat() if row.last_checked_at else None
        ),
    }
