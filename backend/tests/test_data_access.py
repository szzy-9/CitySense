from datetime import datetime

from sqlalchemy import inspect, text

from backend.models import db
from backend.repositories import (
    data_table_counts,
    get_historical_profiles,
    get_sensor_locations_by_ids,
    get_sensor_thresholds,
    list_active_sensor_locations,
    list_database_refuges,
)
from backend.services.city_data import COUNTS_URL, get_pedestrian_snapshot


def test_repository_reads_active_sensors_from_citysense_schema(app):
    with app.app_context():
        _create_ds_tables()
        db.session.execute(
            text(
                """
                INSERT INTO citysense.sensor_location
                    (sensor_id, sensor_description, latitude, longitude, status, source)
                VALUES
                    ('SYNTH-A', 'Fictional SYNTH-A', -37.81, 144.96, 'active', 'DS_TEST'),
                    ('SYNTH-B', 'Fictional SYNTH-B', -37.82, 144.97, 'inactive', 'DS_TEST')
                """
            )
        )
        db.session.commit()

        active = list_active_sensor_locations()
        selected = get_sensor_locations_by_ids(["SYNTH-B"])

    assert active == [
        {
            "location_id": "SYNTH-A",
            "sensor_name": "Fictional SYNTH-A",
            "latitude": -37.81,
            "longitude": 144.96,
            "location_type": None,
            "status": "active",
            "data_source": "DS_TEST",
            "updated_at": None,
        }
    ]
    assert selected[0]["location_id"] == "SYNTH-B"
    assert isinstance(active[0], dict)


def test_profile_repository_maps_ds_fields_and_normalizes_values(app):
    target = datetime.fromisoformat("2026-08-04T08:15:00+10:00")
    with app.app_context():
        _create_ds_tables()
        db.session.execute(
            text(
                """
                INSERT INTO citysense.sensor_load_profile
                    (sensor_id, dow, hour_of_day, median_count, median_per_min,
                     mean_count, mean_per_min, std_dev, n_obs, load_band,
                     confidence, band_version)
                VALUES
                    ('SYNTH-A', 1, 8, 140, 2.5, 150, 2.7, 20, 40,
                     'moderate', 'medium', 'DS_V1'),
                    ('SYNTH-A', 1, 9, 80, 1.3, 90, 1.5, 10, 30,
                     'low', 'high', 'DS_V1')
                """
            )
        )
        db.session.execute(
            text(
                """
                INSERT INTO citysense.sensor_threshold
                    (sensor_id, p50, p80, band_version)
                VALUES ('SYNTH-A', 1.5, 3.5, 'DS_V1')
                """
            )
        )
        db.session.commit()

        profiles = get_historical_profiles(["SYNTH-A"], target)
        thresholds = get_sensor_thresholds(["SYNTH-A"])

    assert profiles["SYNTH-A"] == {
        "location_id": "SYNTH-A",
        "day_of_week": 1,
        "hour_of_day": 8,
        "median_count": 140.0,
        "median_per_min": 2.5,
        "mean_count": 150.0,
        "mean_per_min": 2.7,
        "std_dev": 20.0,
        "sample_count": 40,
        "load_band": "MODERATE",
        "confidence": "MEDIUM",
        "data_version": "DS_V1",
    }
    assert thresholds["SYNTH-A"] == {
        "p50": 1.5,
        "p80": 3.5,
        "data_version": "DS_V1",
    }


def test_live_counts_use_neon_sensor_locations_when_populated(app):
    with app.app_context():
        _create_ds_tables()
        db.session.execute(
            text(
                """
                INSERT INTO citysense.sensor_location
                    (sensor_id, sensor_description, latitude, longitude, status, source)
                VALUES
                    ('SYNTH-A', 'Fictional SYNTH-A', -37.81, 144.96, 'active', 'DS_TEST')
                """
            )
        )
        db.session.commit()
        fake_client = FakeCityClient()

        snapshot = get_pedestrian_snapshot(
            use_live=True,
            timeout=1,
            client=fake_client,
        )

    assert snapshot["source"] == "live"
    assert snapshot["sensor_location_source"] == "NEON"
    assert snapshot["sensors"][0]["name"] == "Fictional SYNTH-A"
    assert snapshot["readings"] == [
        {
            "location_id": "SYNTH-A",
            "sensed_at": "2026-08-06T00:00:00+00:00",
            "total_count": 125,
            "interval_minutes": 1,
            "source": "LIVE",
        }
    ]
    assert fake_client.urls == [COUNTS_URL]


def test_missing_live_count_is_not_normalised_to_zero_or_low():
    from backend.services.city_data import _join_live_rows

    snapshot = _join_live_rows(
        [{"location_id": "SYNTH-A", "total_count": None}],
        [
            {
                "location_id": "SYNTH-A",
                "sensor_description": "Fictional SYNTH-A",
                "latitude": -37.81,
                "longitude": 144.96,
            }
        ],
    )

    assert snapshot["sensors"] == []
    assert snapshot["readings"] == []
    assert snapshot["updated_at"] is None


def test_refuge_api_joins_citysense_opening_hours(app, client):
    with app.app_context():
        _create_ds_tables()
        db.session.execute(
            text(
                """
                INSERT INTO citysense.refuge
                    (id, name, lat, lon, type, setting, seating, shaded,
                     description, verified, source)
                VALUES
                    ('SYNTH-REFUGE', 'Fictional Neon Refuge', -37.81, 144.96,
                     'Test space', 'Indoor', 1, 0, 'Fictional test record', 0,
                     'DS_TEST')
                """
            )
        )
        db.session.execute(
            text(
                """
                INSERT INTO citysense.refuge_opening_hours
                    (refuge_id, weekday, open_time, close_time, is_closed)
                VALUES ('SYNTH-REFUGE', 'Monday', '09:00', '17:00', 0)
                """
            )
        )
        db.session.commit()
        assert isinstance(list_database_refuges()[0], dict)

    response = client.get("/api/refuges")
    body = response.get_json()

    assert response.status_code == 200
    assert body["data_status"]["source"] == "neon"
    assert body["refuges"][0]["id"] == "SYNTH-REFUGE"
    assert body["refuges"][0]["availability"] == "Monday: 09:00-17:00"
    assert body["data_status"]["verified"] is False


def test_data_status_counts_only_ds_tables_and_keeps_live_readings_unpersisted(app):
    with app.app_context():
        _create_ds_tables()
        counts = data_table_counts()
        public_tables = inspect(db.engine).get_table_names()

    assert counts == {
        "sensor_locations": 0,
        "historical_profiles": 0,
        "sensor_thresholds": 0,
        "refuges": 0,
        "refuge_opening_hours": 0,
        "pedestrian_readings": None,
    }
    assert public_tables == ["route_searches"]


def _create_ds_tables():
    db.session.execute(text("ATTACH DATABASE ':memory:' AS citysense"))
    statements = [
        """
        CREATE TABLE citysense.sensor_location (
            sensor_id TEXT PRIMARY KEY,
            sensor_description TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            status TEXT,
            source TEXT,
            updated_at TEXT
        )
        """,
        """
        CREATE TABLE citysense.sensor_load_profile (
            sensor_id TEXT NOT NULL,
            dow INTEGER NOT NULL,
            hour_of_day INTEGER NOT NULL,
            median_count REAL,
            median_per_min REAL,
            mean_count REAL,
            mean_per_min REAL,
            std_dev REAL,
            n_obs INTEGER,
            load_band TEXT,
            confidence TEXT,
            band_version TEXT
        )
        """,
        """
        CREATE TABLE citysense.sensor_threshold (
            sensor_id TEXT PRIMARY KEY,
            p50 REAL,
            p80 REAL,
            band_version TEXT
        )
        """,
        """
        CREATE TABLE citysense.refuge (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            type TEXT,
            setting TEXT,
            seating INTEGER,
            shaded INTEGER,
            description TEXT,
            verified INTEGER,
            source TEXT,
            updated_at TEXT
        )
        """,
        """
        CREATE TABLE citysense.refuge_opening_hours (
            refuge_id TEXT NOT NULL,
            weekday TEXT,
            open_time TEXT,
            close_time TEXT,
            is_closed INTEGER
        )
        """,
    ]
    for statement in statements:
        db.session.execute(text(statement))
    db.session.commit()


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "results": [
                {
                    "location_id": "SYNTH-A",
                    "sensing_datetime": "2026-08-06T00:00:00+00:00",
                    "total_of_directions": 125,
                }
            ]
        }


class FakeCityClient:
    def __init__(self):
        self.urls = []

    def get(self, url, params=None):
        self.urls.append(url)
        return FakeResponse()
