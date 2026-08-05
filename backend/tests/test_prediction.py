from datetime import datetime

import pytest

from backend.services.prediction import (
    add_historical_predictions,
    parse_departure_time,
    prediction_confidence,
)


THRESHOLDS = {
    "medium_min_samples": 12,
    "high_min_samples": 30,
    "medium_max_cv": 1.0,
    "high_max_cv": 0.5,
    "minimum_alert_confidence": "MEDIUM",
}


def test_missing_profiles_return_explicit_unavailable_result():
    routes = [_route()]
    departure, _defaulted = parse_departure_time("2026-08-04T08:00:00+10:00")

    add_historical_predictions(routes, departure, "LOW", THRESHOLDS, {})

    assert routes[0]["historical_prediction_available"] is False
    assert routes[0]["predicted_count"] is None
    assert routes[0]["predicted_peak"] == "NO_DATA"
    assert routes[0]["prediction_alert"] is None


def test_historical_median_uses_existing_load_bands_and_can_create_alert():
    routes = [_route()]
    departure, _defaulted = parse_departure_time("2026-08-04T08:00:00+10:00")
    lookup = {
        ("SYNTH-SENSOR-001", 1, 8): _profile(620, 40, 620, 80),
    }

    add_historical_predictions(routes, departure, "LOW", THRESHOLDS, lookup)

    prediction = routes[0]
    assert prediction["historical_prediction_available"] is True
    assert prediction["predicted_peak"] == "HIGH"
    assert prediction["predicted_count"] == 620
    assert prediction["prediction_confidence"] == "HIGH"
    assert routes[0]["prediction_alert"]["lead_minutes"] == 10
    assert routes[0]["segments"][0]["estimated_arrival_time"].startswith(
        "2026-08-04T08:10"
    )


def test_multiple_matching_sensors_use_the_highest_predicted_band():
    route = _route()
    route["segments"][0]["matched_sensor_ids"] = [
        "SYNTH-SENSOR-001",
        "SYNTH-SENSOR-002",
    ]
    route["segments"][1]["matched_sensor_ids"] = ["SYNTH-SENSOR-001"]
    departure, _defaulted = parse_departure_time("2026-08-04T08:00:00+10:00")
    lookup = {
        ("SYNTH-SENSOR-001", 1, 8): _profile(120, 40, 120, 10),
        ("SYNTH-SENSOR-002", 1, 8): _profile(620, 40, 620, 50),
    }

    add_historical_predictions([route], departure, "LOW", THRESHOLDS, lookup)

    assert route["segments"][0]["predicted_band"] == "HIGH"
    assert route["predicted_peak"] == "HIGH"


def test_low_confidence_profile_does_not_create_a_normal_alert():
    route = _route()
    departure, _defaulted = parse_departure_time("2026-08-04T08:00:00+10:00")
    lookup = {
        ("SYNTH-SENSOR-001", 1, 8): _profile(620, 2, 620, 500),
    }

    configured_too_low = {**THRESHOLDS, "minimum_alert_confidence": "LOW"}
    add_historical_predictions(
        [route], departure, "LOW", configured_too_low, lookup
    )

    assert route["prediction_confidence"] == "LOW"
    assert route["prediction_alert"] is None


def test_prototype_route_never_has_high_prediction_confidence_or_alert():
    route = _route()
    route["route_source"] = "fallback"
    departure, _defaulted = parse_departure_time("2026-08-04T08:00:00+10:00")
    lookup = {
        ("SYNTH-SENSOR-001", 1, 8): _profile(620, 40, 620, 10),
    }

    add_historical_predictions([route], departure, "LOW", THRESHOLDS, lookup)

    assert route["prediction_confidence"] == "LOW"
    assert route["prediction_alert"] is None


def test_prediction_confidence_handles_zero_mean_without_division_error():
    assert prediction_confidence(_profile(0, 40, 0, 0), THRESHOLDS) == "HIGH"
    assert prediction_confidence(_profile(0, 40, 0, 1), THRESHOLDS) == "LOW"


def test_departure_time_requires_timezone_and_defaults_to_melbourne():
    with pytest.raises(ValueError, match="timezone"):
        parse_departure_time("2026-08-04T08:00:00")

    parsed, defaulted = parse_departure_time(
        None,
        now=datetime.fromisoformat("2026-08-04T00:00:00+00:00"),
    )
    assert defaulted is True
    assert parsed.tzinfo is not None
    assert parsed.hour == 10


def _route():
    return {
        "id": "route-live",
        "route_source": "live",
        "duration_minutes": 20,
        "segments": [
            {
                "id": "segment-1",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[144.96, -37.81], [144.965, -37.81]],
                },
                "matched_sensor_ids": ["SYNTH-SENSOR-001"],
            },
            {
                "id": "segment-2",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[144.965, -37.81], [144.97, -37.81]],
                },
                "matched_sensor_ids": ["SYNTH-SENSOR-001"],
            },
        ],
    }


def _profile(median, samples, mean, standard_deviation):
    return {
        "median_count": median,
        "sample_count": samples,
        "mean_count": mean,
        "std_dev": standard_deviation,
        "data_version": "SYNTHETIC_V1",
    }
