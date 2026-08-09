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


def test_repository_reads_cbd_sensors_without_interpreting_status(app):
    with app.app_context():
        _create_ds_tables()
        db.session.execute(
            text(
                """
                INSERT INTO citysense.sensor_location
                    (location_id, sensor_description, sensor_name,
                     location_type, status, latitude, longitude, in_cbd)
                VALUES
                    (101, 'Fictional sensor A', 'SYNTH-A', 'Outdoor',
                     'A', -37.81, 144.96, 1),
                    (102, 'Fictional sensor B', 'SYNTH-B', 'Indoor',
                     'I', -37.82, 144.97, 1),
                    (103, 'Outside CBD', 'SYNTH-C', 'Outdoor',
                     'A', -37.70, 144.80, 0)
                """
            )
        )
        db.session.commit()

        active = list_active_sensor_locations()
        selected = get_sensor_locations_by_ids(["102"])

    assert active == [
        {
            "location_id": "101",
            "sensor_name": "SYNTH-A",
            "latitude": -37.81,
            "longitude": 144.96,
            "location_type": "Outdoor",
            "status": "A",
            "data_source": "NEON",
            "updated_at": None,
        },
        {
            "location_id": "102",
            "sensor_name": "SYNTH-B",
            "latitude": -37.82,
            "longitude": 144.97,
            "location_type": "Indoor",
            "status": "I",
            "data_source": "NEON",
            "updated_at": None,
        },
    ]
    assert selected[0]["location_id"] == "102"
    assert isinstance(active[0], dict)


def test_profile_repository_maps_ds_fields_and_normalizes_values(app):
    target = datetime.fromisoformat("2026-08-04T08:15:00+10:00")
    with app.app_context():
        _create_ds_tables()
        db.session.execute(
            text(
                """
                INSERT INTO citysense.sensor_load_profile
                    (location_id, dow, hour_of_day, median_count, median_per_min,
                     mean_count, mean_per_min, std_dev, n_obs, load_band,
                     confidence, band_version)
                VALUES
                    (101, 1, 8, 140, 2.5, 150, 2.7, 20, 40,
                     'moderate', 'medium', 'DS_V1'),
                    (101, 1, 9, 80, 1.3, 90, 1.5, 10, 30,
                     'low', 'high', 'DS_V1')
                """
            )
        )
        db.session.execute(
            text(
                """
                INSERT INTO citysense.sensor_threshold
                    (location_id, p50, p80, first_seen, last_seen, completeness)
                VALUES (101, 1.5, 3.5, '2025-01-01', '2026-07-31', 0.9876)
                """
            )
        )
        db.session.commit()

        profiles = get_historical_profiles(["101"], target)
        thresholds = get_sensor_thresholds(["101"])

    assert profiles["101"] == {
        "location_id": "101",
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
    assert thresholds["101"] == {
        "p50": 1.5,
        "p80": 3.5,
        "first_seen": "2025-01-01",
        "last_seen": "2026-07-31",
        "completeness": 0.9876,
    }
    assert "data_version" not in thresholds["101"]


def test_profile_repository_treats_invalid_ds_labels_conservatively(app):
    target = datetime.fromisoformat("2026-08-04T10:15:00+10:00")
    with app.app_context():
        _create_ds_tables()
        db.session.execute(
            text(
                """
                INSERT INTO citysense.sensor_load_profile
                    (location_id, dow, hour_of_day, median_count, median_per_min,
                     mean_count, mean_per_min, std_dev, n_obs, load_band,
                     confidence, band_version)
                VALUES
                    (101, 1, 10, 140, 2.5, 150, 2.7, 20, 40,
                     'unexpected', 'uncertain', 'DS_V1')
                """
            )
        )
        db.session.commit()

        profile = get_historical_profiles(["101"], target)["101"]

    assert profile["load_band"] == "NO_DATA"
    assert profile["confidence"] == "LOW"


def test_live_counts_use_neon_sensor_locations_when_populated(app):
    with app.app_context():
        _create_ds_tables()
        db.session.execute(
            text(
                """
                INSERT INTO citysense.sensor_location
                    (location_id, sensor_description, sensor_name,
                     location_type, status, latitude, longitude, in_cbd)
                VALUES
                    (101, 'Fictional sensor A', 'SYNTH-A', 'Outdoor',
                     'A', -37.81, 144.96, 1)
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
    assert snapshot["sensors"][0]["name"] == "SYNTH-A"
    assert snapshot["readings"] == [
        {
            "location_id": "101",
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
                INSERT INTO citysense.landmark_category
                    (category_id, theme_id, sub_theme)
                VALUES (7, 2, 'Library forecourt')
                """
            )
        )
        db.session.execute(
            text(
                """
                INSERT INTO citysense.landmark
                    (landmark_id, category_id)
                VALUES (11, 7)
                """
            )
        )
        db.session.execute(
            text(
                """
                INSERT INTO citysense.refuge
                    (refuge_id, landmark_id, refuge_name, latitude, longitude,
                     indoor_outdoor, has_seating, lighting_level, step_free,
                     verified_by, verified_on, source_note)
                VALUES
                    (201, 11, 'Fictional Neon Refuge', -37.81, 144.96,
                     'Outdoor', 1, 'Low', 1, 'DS Team', '2026-07-30',
                     'Fictional test record')
                """
            )
        )
        db.session.execute(
            text(
                """
                INSERT INTO citysense.refuge_opening_hours
                    (refuge_id, dow, opens_at, closes_at)
                VALUES
                    (201, 0, '09:00', '12:00'),
                    (201, 0, '13:00', '17:00'),
                    (201, 1, '10:00', '16:00')
                """
            )
        )
        db.session.commit()
        assert isinstance(list_database_refuges()[0], dict)

    response = client.get("/api/refuges")
    body = response.get_json()

    assert response.status_code == 200
    assert body["data_status"]["source"] == "neon"
    refuge = body["refuges"][0]
    assert refuge["id"] == "201"
    assert refuge["refuge_type"] == "Library forecourt"
    assert refuge["availability"] == (
        "Mon 09:00-12:00, 13:00-17:00; Tue 10:00-16:00"
    )
    assert refuge["is_shaded"] is None
    assert refuge["step_free"] is True
    assert refuge["short_description"] == "Fictional test record"
    assert refuge["last_checked_at"] == "2026-07-30"
    assert body["data_status"]["verified"] is True


def test_data_status_counts_only_ds_tables_and_keeps_live_readings_unpersisted(
    app, client
):
    with app.app_context():
        _create_ds_tables()
        counts = data_table_counts()
        public_tables = inspect(db.engine).get_table_names()

    response = client.get("/api/data/status")

    assert counts == {
        "sensor_locations": 0,
        "historical_profiles": 0,
        "sensor_thresholds": 0,
        "refuges": 0,
        "refuge_opening_hours": 0,
        "pedestrian_readings": None,
    }
    assert public_tables == []
    assert response.status_code == 200
    assert set(response.get_json()) == set(counts)


def _create_ds_tables():
    db.session.execute(text("ATTACH DATABASE ':memory:' AS citysense"))
    statements = [
        """
        CREATE TABLE citysense.sensor_location (
            location_id INTEGER PRIMARY KEY,
            sensor_description TEXT NOT NULL,
            sensor_name TEXT NOT NULL,
            installation_date DATE,
            location_type TEXT NOT NULL,
            status CHAR(1) NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            note TEXT,
            in_cbd BOOLEAN NOT NULL DEFAULT 0
        )
        """,
        """
        CREATE TABLE citysense.sensor_load_profile (
            location_id INTEGER NOT NULL,
            dow INTEGER NOT NULL,
            hour_of_day INTEGER NOT NULL,
            median_count REAL NOT NULL,
            median_per_min REAL NOT NULL,
            mean_count REAL NOT NULL,
            mean_per_min REAL NOT NULL,
            std_dev REAL NOT NULL,
            n_obs INTEGER NOT NULL,
            load_band TEXT NOT NULL,
            confidence TEXT NOT NULL,
            band_version TEXT NOT NULL,
            PRIMARY KEY (location_id, dow, hour_of_day)
        )
        """,
        """
        CREATE TABLE citysense.sensor_threshold (
            location_id INTEGER PRIMARY KEY,
            p50 REAL NOT NULL,
            p80 REAL NOT NULL,
            first_seen DATE NOT NULL,
            last_seen DATE NOT NULL,
            completeness REAL NOT NULL
        )
        """,
        """
        CREATE TABLE citysense.landmark_category (
            category_id INTEGER PRIMARY KEY,
            theme_id INTEGER NOT NULL,
            sub_theme TEXT
        )
        """,
        """
        CREATE TABLE citysense.landmark (
            landmark_id INTEGER PRIMARY KEY,
            category_id INTEGER
        )
        """,
        """
        CREATE TABLE citysense.refuge (
            refuge_id INTEGER PRIMARY KEY,
            landmark_id INTEGER,
            refuge_name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            indoor_outdoor TEXT NOT NULL,
            has_seating BOOLEAN NOT NULL,
            lighting_level TEXT,
            step_free BOOLEAN,
            verified_by TEXT NOT NULL,
            verified_on DATE NOT NULL,
            source_note TEXT
        )
        """,
        """
        CREATE TABLE citysense.refuge_opening_hours (
            refuge_id INTEGER NOT NULL,
            dow INTEGER NOT NULL,
            opens_at TIME NOT NULL,
            closes_at TIME NOT NULL,
            PRIMARY KEY (refuge_id, dow, opens_at)
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
                    "location_id": 101,
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
