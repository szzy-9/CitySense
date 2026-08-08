from datetime import datetime, timezone

from backend.models import Refuge, SensorHistoricalProfile, SensorLocation, db
from backend.repositories import (
    get_historical_profiles,
    get_sensor_locations_by_ids,
    list_active_sensor_locations,
    list_database_refuges,
)
from backend.services.city_data import COUNTS_URL, _join_live_rows, get_pedestrian_snapshot


def test_repository_returns_plain_active_sensor_dictionaries(app):
    with app.app_context():
        db.session.add_all(
            [
                _sensor("SYNTH-A", "active"),
                _sensor("SYNTH-B", "inactive"),
            ]
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
            "data_source": "SYNTHETIC_TEST",
            "updated_at": None,
        }
    ]
    assert selected[0]["location_id"] == "SYNTH-B"
    assert isinstance(active[0], dict)


def test_historical_profile_repository_uses_weekday_and_hour(app):
    target = datetime.fromisoformat("2026-08-04T08:15:00+10:00")
    with app.app_context():
        db.session.add(_sensor("SYNTH-A", "active"))
        db.session.add(
            SensorHistoricalProfile(
                location_id="SYNTH-A",
                day_of_week=target.weekday(),
                hour_of_day=target.hour,
                mean_count=150,
                median_count=140,
                percentile_80=175,
                std_dev=20,
                sample_count=40,
                source_period_start=datetime(2025, 1, 1).date(),
                source_period_end=datetime(2025, 12, 31).date(),
                generated_at=datetime.now(timezone.utc),
                data_version="SYNTHETIC_V1",
            )
        )
        db.session.commit()

        profiles = get_historical_profiles(["SYNTH-A"], target)

    assert profiles["SYNTH-A"]["median_count"] == 140
    assert profiles["SYNTH-A"]["sample_count"] == 40


def test_live_counts_use_database_sensor_locations_when_populated(app):
    with app.app_context():
        db.session.add(_sensor("SYNTH-A", "active"))
        db.session.commit()
        fake_client = FakeCityClient()

        snapshot = get_pedestrian_snapshot(
            use_live=True,
            timeout=1,
            client=fake_client,
        )

    assert snapshot["source"] == "live"
    assert snapshot["sensor_location_source"] == "DATABASE"
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


def test_refuge_api_prefers_database_rows_and_keeps_plain_output(app, client):
    with app.app_context():
        db.session.add(
            Refuge(
                refuge_id="SYNTH-REFUGE",
                name="Fictional Database Refuge",
                latitude=-37.81,
                longitude=144.96,
                refuge_type="Test space",
                short_description="Fictional test record",
                opening_hours="Test availability only",
                verified=False,
                data_source="SYNTHETIC_TEST",
            )
        )
        db.session.commit()
        assert isinstance(list_database_refuges()[0], dict)

    response = client.get("/api/refuges")
    body = response.get_json()

    assert response.status_code == 200
    assert body["data_status"]["source"] == "database"
    assert body["refuges"][0]["id"] == "SYNTH-REFUGE"
    assert body["data_status"]["verified"] is False


def _sensor(identifier, status):
    return SensorLocation(
        location_id=identifier,
        sensor_name=f"Fictional {identifier}",
        latitude=-37.81,
        longitude=144.96,
        status=status,
        data_source="SYNTHETIC_TEST",
    )


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
