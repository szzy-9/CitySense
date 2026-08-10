from pathlib import Path

import pytest
from sqlalchemy import inspect

from backend.models import db
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


def test_loader_refuses_to_write_ds_managed_data(app):
    files = {
        "sensor_locations": FIXTURES / "sensor_locations.csv",
        "pedestrian_readings": FIXTURES / "pedestrian_readings.csv",
        "historical_profiles": FIXTURES / "sensor_historical_profiles.csv",
        "refuges": FIXTURES / "refuges.csv",
    }

    with pytest.raises(RuntimeError, match="DS team"):
        load_datasets(files, app=app)


def test_loader_dry_run_does_not_write(app):
    files = {"sensor_locations": FIXTURES / "sensor_locations.csv"}

    result = load_datasets(files, dry_run=True, app=app)

    assert result == {"sensor_locations": 2}
    with app.app_context():
        assert "sensor_locations" not in inspect(db.engine).get_table_names()


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


def test_application_initialization_creates_no_tables(app):
    with app.app_context():
        assert inspect(db.engine).get_table_names() == []
