from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, Index, UniqueConstraint


db = SQLAlchemy()


class SensorLocation(db.Model):
    __tablename__ = "sensor_locations"

    location_id = db.Column(db.String(80), primary_key=True)
    sensor_name = db.Column(db.String(200), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    location_type = db.Column(db.String(80), nullable=True)
    status = db.Column(db.String(30), nullable=True)
    data_source = db.Column(db.String(80), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_sensor_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_sensor_longitude"),
        Index("idx_sensor_locations_status", "status"),
    )


class PedestrianReading(db.Model):
    __tablename__ = "pedestrian_readings"

    reading_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    location_id = db.Column(
        db.String(80),
        db.ForeignKey("sensor_locations.location_id"),
        nullable=False,
    )
    sensed_at = db.Column(db.DateTime(timezone=True), nullable=False)
    direction_1 = db.Column(db.Integer, nullable=True)
    direction_2 = db.Column(db.Integer, nullable=True)
    total_count = db.Column(db.Integer, nullable=False)
    interval_minutes = db.Column(db.Integer, nullable=False)
    source = db.Column(db.String(80), nullable=False)
    fetched_at = db.Column(db.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("total_count >= 0", name="ck_reading_total_count"),
        CheckConstraint(
            "direction_1 IS NULL OR direction_1 >= 0",
            name="ck_reading_direction_1",
        ),
        CheckConstraint(
            "direction_2 IS NULL OR direction_2 >= 0",
            name="ck_reading_direction_2",
        ),
        CheckConstraint("interval_minutes > 0", name="ck_reading_interval"),
        UniqueConstraint(
            "location_id",
            "sensed_at",
            "interval_minutes",
            "source",
            name="uq_pedestrian_reading_identity",
        ),
        Index("idx_pedestrian_readings_sensed_at", "sensed_at"),
        Index("idx_pedestrian_readings_location_time", "location_id", "sensed_at"),
    )


class SensorHistoricalProfile(db.Model):
    __tablename__ = "sensor_historical_profiles"

    location_id = db.Column(
        db.String(80),
        db.ForeignKey("sensor_locations.location_id"),
        primary_key=True,
    )
    day_of_week = db.Column(db.Integer, primary_key=True)
    hour_of_day = db.Column(db.Integer, primary_key=True)
    mean_count = db.Column(db.Float, nullable=False)
    median_count = db.Column(db.Float, nullable=False)
    percentile_80 = db.Column(db.Float, nullable=False)
    std_dev = db.Column(db.Float, nullable=False)
    sample_count = db.Column(db.Integer, nullable=False)
    generated_at = db.Column(db.DateTime(timezone=True), nullable=False)
    source_period_start = db.Column(db.Date, nullable=False)
    source_period_end = db.Column(db.Date, nullable=False)
    data_version = db.Column(db.String(40), nullable=False)

    __table_args__ = (
        CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="ck_profile_day"),
        CheckConstraint("hour_of_day >= 0 AND hour_of_day <= 23", name="ck_profile_hour"),
        CheckConstraint("mean_count >= 0", name="ck_profile_mean"),
        CheckConstraint("median_count >= 0", name="ck_profile_median"),
        CheckConstraint("percentile_80 >= 0", name="ck_profile_percentile_80"),
        CheckConstraint("std_dev >= 0", name="ck_profile_std_dev"),
        CheckConstraint("sample_count >= 0", name="ck_profile_samples"),
        CheckConstraint(
            "source_period_end >= source_period_start",
            name="ck_profile_source_period",
        ),
        Index("idx_profiles_day_hour", "day_of_week", "hour_of_day"),
    )


class Refuge(db.Model):
    __tablename__ = "refuges"

    refuge_id = db.Column(db.String(80), primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    refuge_type = db.Column(db.String(80), nullable=False)
    indoor_outdoor = db.Column(db.String(40), nullable=True)
    has_seating = db.Column(db.Boolean, nullable=True)
    is_shaded = db.Column(db.Boolean, nullable=True)
    lighting_level = db.Column(db.String(80), nullable=True)
    opening_hours = db.Column(db.String(200), nullable=True)
    short_description = db.Column(db.String(300), nullable=False)
    verified = db.Column(db.Boolean, nullable=False, default=False)
    data_source = db.Column(db.String(80), nullable=True)
    last_checked_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_refuge_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_refuge_longitude"),
    )


class RouteSearch(db.Model):
    __tablename__ = "route_searches"

    id = db.Column(db.Integer, primary_key=True)
    # Legacy database column names are retained so existing local databases work.
    start_source = db.Column("start_id", db.String(80), nullable=False)
    end_source = db.Column("end_id", db.String(80), nullable=False)
    fastest_route_id = db.Column(db.String(40), nullable=False)
    calmest_route_id = db.Column(db.String(40), nullable=False)
    route_source = db.Column(db.String(20), nullable=False)
    pedestrian_source = db.Column(db.String(20), nullable=False)
    selected_route_type = db.Column(db.String(40), nullable=True)
    confidence = db.Column(db.String(10), nullable=True)
    route_count = db.Column(db.Integer, nullable=True)
    used_historical_prediction = db.Column(db.Boolean, nullable=True)
    prediction_confidence = db.Column(db.String(10), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
