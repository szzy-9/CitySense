from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine, inspect, text

from backend.app import create_app
from backend.models import PedestrianReading, SensorLocation, db
from scripts import load_data
from scripts.load_data import load_datasets
from scripts.validate_data import validate_dataset, validate_files


FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "data"


def test_valid_synthetic_files_pass_with_foreign_keys():
    results = validate_files(
        {
            "sensor_locations": FIXTURES / "sensor_locations.csv",
            "pedestrian_readings": FIXTURES / "pedestrian_readings.csv",
            "historical_profiles": FIXTURES / "sensor_historical_profiles.csv",
            "refuges": FIXTURES / "refuges.csv",
        }
    )

    assert all(result.valid for result in results.values())
    assert results["sensor_locations"].row_count == 2


@pytest.mark.parametrize(
    ("dataset", "filename"),
    [
        ("sensor_locations", "invalid_sensor_locations.csv"),
        ("pedestrian_readings", "invalid_pedestrian_readings.csv"),
        ("historical_profiles", "invalid_sensor_historical_profiles.csv"),
        ("refuges", "invalid_refuges.csv"),
    ],
)
def test_invalid_fixture_reports_row_level_errors(dataset, filename):
    result = validate_dataset(dataset, FIXTURES / filename, set())

    assert result.valid is False
    assert any(error.startswith("Row 2:") for error in result.errors)


def test_duplicate_natural_key_is_reported():
    result = validate_dataset(
        "sensor_locations", FIXTURES / "invalid_sensor_locations.csv"
    )

    assert any("duplicate key SYNTH-DUP" in error for error in result.errors)

    profiles = validate_dataset(
        "historical_profiles",
        FIXTURES / "invalid_sensor_historical_profiles.csv",
        set(),
    )
    assert any("duplicate key MISSING-SENSOR/7/24" in error for error in profiles.errors)
    assert any("not present in sensor locations" in error for error in profiles.errors)


def test_empty_header_only_and_example_files_are_not_loadable_data():
    empty = validate_dataset("refuges", FIXTURES / "empty.csv")
    header_only = validate_dataset(
        "historical_profiles", FIXTURES / "header_only_profiles.csv"
    )
    example = validate_dataset(
        "sensor_locations",
        Path(__file__).resolve().parents[2]
        / "data"
        / "templates"
        / "sensor_locations.csv.example",
    )

    assert empty.valid is False
    assert header_only.valid is True
    assert header_only.row_count == 0
    assert header_only.warnings
    assert example.skipped is True


def test_explicit_example_can_be_checked_as_header_only_schema():
    example = validate_dataset(
        "sensor_locations",
        Path(__file__).resolve().parents[2]
        / "data"
        / "templates"
        / "sensor_locations.csv.example",
        allow_example=True,
    )

    assert example.valid is True
    assert example.skipped is False
    assert example.row_count == 0
    assert example.warnings


def test_wrong_csv_header_fails(tmp_path):
    wrong = tmp_path / "sensor_locations.csv"
    wrong.write_text("location_id,wrong_name\nSYNTH-A,value\n", encoding="utf-8")

    result = validate_dataset("sensor_locations", wrong)

    assert result.valid is False
    assert "Header mismatch" in result.errors[0]


def test_loader_is_idempotent_with_synthetic_files(app):
    files = {
        "sensor_locations": FIXTURES / "sensor_locations.csv",
        "pedestrian_readings": FIXTURES / "pedestrian_readings.csv",
        "historical_profiles": FIXTURES / "sensor_historical_profiles.csv",
        "refuges": FIXTURES / "refuges.csv",
    }

    first = load_datasets(files, app=app)
    second = load_datasets(files, app=app)

    assert first == second
    with app.app_context():
        assert SensorLocation.query.count() == 2


def test_loader_handles_more_rows_than_sqlite_bind_variable_limit(app, tmp_path):
    """A real extract exceeds SQLite's bind-variable cap in a single INSERT."""
    sensors = tmp_path / "sensor_locations.csv"
    sensors.write_text(
        "location_id,sensor_name,latitude,longitude,location_type,status,"
        "data_source,updated_at\n"
        "SYNTH-BULK,Fictional bulk sensor,-37.81,144.96,pedestrian_counter,"
        "active,SYNTHETIC_TEST,2026-01-01T00:00:00+00:00\n",
        encoding="utf-8",
    )

    # Eight columns per row, so this clears SQLite's 32766-variable ceiling for
    # a single multi-row INSERT and fails unless the loader chunks.
    row_count = 4200
    lines = [
        "location_id,sensed_at,direction_1,direction_2,total_count,"
        "interval_minutes,source,fetched_at"
    ]
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for index in range(row_count):
        sensed_at = (base + timedelta(hours=index)).isoformat()
        lines.append(
            f"SYNTH-BULK,{sensed_at},1,2,3,60,"
            "SYNTHETIC_TEST,2026-01-01T00:00:00+00:00"
        )
    readings = tmp_path / "pedestrian_readings.csv"
    readings.write_text("\n".join(lines) + "\n", encoding="utf-8")

    loaded = load_datasets(
        {"sensor_locations": sensors, "pedestrian_readings": readings},
        app=app,
    )

    assert loaded["pedestrian_readings"] == row_count
    with app.app_context():
        assert PedestrianReading.query.count() == row_count


def test_loader_dry_run_does_not_write(app):
    files = {"sensor_locations": FIXTURES / "sensor_locations.csv"}

    result = load_datasets(files, dry_run=True, app=app)

    assert result == {"sensor_locations": 2}
    with app.app_context():
        assert SensorLocation.query.count() == 0


def test_missing_optional_files_are_reported_and_strict_mode_fails(
    monkeypatch,
    capsys,
    tmp_path,
):
    # Point the standard paths at an empty directory so the result does not
    # depend on whether this developer machine has real processed extracts.
    monkeypatch.setattr(
        load_data,
        "DEFAULT_FILES",
        {
            dataset: tmp_path / path.name
            for dataset, path in load_data.DEFAULT_FILES.items()
        },
    )

    monkeypatch.setattr("sys.argv", ["load_data.py", "--dry-run"])
    assert load_data.main() == 1
    assert "Skipped missing optional dataset" in capsys.readouterr().out

    monkeypatch.setattr("sys.argv", ["load_data.py", "--dry-run", "--strict"])
    assert load_data.main() == 1
    assert "fatal" in capsys.readouterr().out


def test_database_coordinate_constraint_rejects_invalid_sensor(app):
    with app.app_context():
        db.session.add(
            SensorLocation(
                location_id="SYNTH-INVALID",
                sensor_name="Fictional invalid sensor",
                latitude=100,
                longitude=144.96,
                data_source="SYNTHETIC_TEST",
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_old_route_search_table_gets_additive_metadata_columns(tmp_path):
    database_path = tmp_path / "legacy.db"
    url = f"sqlite:///{database_path.as_posix()}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE route_searches (
                    id INTEGER PRIMARY KEY,
                    start_id VARCHAR(80) NOT NULL,
                    end_id VARCHAR(80) NOT NULL,
                    fastest_route_id VARCHAR(40) NOT NULL,
                    calmest_route_id VARCHAR(40) NOT NULL,
                    route_source VARCHAR(20) NOT NULL,
                    pedestrian_source VARCHAR(20) NOT NULL,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )
    engine.dispose()

    legacy_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": url,
            "USE_LIVE_CITY_DATA": False,
            "ORS_API_KEY": "",
            "FRONTEND_ORIGIN": "http://127.0.0.1:5173",
        }
    )
    with legacy_app.app_context():
        columns = {column["name"] for column in inspect(db.engine).get_columns("route_searches")}
        db.session.remove()
        db.engine.dispose()

    assert {
        "selected_route_type",
        "confidence",
        "route_count",
        "used_historical_prediction",
        "prediction_confidence",
    }.issubset(columns)
