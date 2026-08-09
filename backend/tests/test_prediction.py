from datetime import datetime

import pytest

from backend.services.prediction import (
    MELBOURNE_TIMEZONE,
    add_historical_predictions,
    parse_departure_time,
    prediction_confidence,
    suggest_calmer_departure,
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


def test_profile_without_ds_load_band_is_not_independently_classified():
    routes = [_route()]
    departure, _defaulted = parse_departure_time("2026-08-04T08:00:00+10:00")
    lookup = {
        ("SYNTH-SENSOR-001", 1, 8): {
            "median_per_min": 200,
            "sample_count": 40,
            "confidence": "high",
            "data_version": "SYNTHETIC_V1",
        }
    }

    add_historical_predictions(routes, departure, "LOW", THRESHOLDS, lookup)

    assert routes[0]["historical_prediction_available"] is False
    assert routes[0]["predicted_peak"] == "NO_DATA"


def test_ds_median_per_min_load_band_and_confidence_create_alert():
    routes = [_route()]
    departure, _defaulted = parse_departure_time("2026-08-04T08:00:00+10:00")
    lookup = {
        ("SYNTH-SENSOR-001", 1, 8): _profile(
            200,
            40,
            "high",
            "high",
            median_count=60,
        ),
    }

    add_historical_predictions(routes, departure, "LOW", THRESHOLDS, lookup)

    prediction = routes[0]
    assert prediction["historical_prediction_available"] is True
    assert prediction["predicted_peak"] == "HIGH"
    assert prediction["predicted_count"] == 200
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
        ("SYNTH-SENSOR-001", 1, 8): _profile(2, 40, "low", "high"),
        ("SYNTH-SENSOR-002", 1, 8): _profile(200, 40, "high", "high"),
    }

    add_historical_predictions([route], departure, "LOW", THRESHOLDS, lookup)

    assert route["segments"][0]["predicted_band"] == "HIGH"
    assert route["predicted_peak"] == "HIGH"


def test_low_confidence_profile_does_not_create_a_normal_alert():
    route = _route()
    departure, _defaulted = parse_departure_time("2026-08-04T08:00:00+10:00")
    lookup = {
        ("SYNTH-SENSOR-001", 1, 8): _profile(200, 2, "high", "low"),
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
        ("SYNTH-SENSOR-001", 1, 8): _profile(200, 40, "high", "high"),
    }

    add_historical_predictions([route], departure, "LOW", THRESHOLDS, lookup)

    assert route["prediction_confidence"] == "LOW"
    assert route["prediction_alert"] is None


def test_prediction_confidence_uses_normalized_ds_value():
    assert prediction_confidence(_profile(0, 40, "low", "high"), THRESHOLDS) == "HIGH"
    assert prediction_confidence(_profile(0, 40, "low", "unknown"), THRESHOLDS) == "LOW"


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


def _profile(rate, samples, band, confidence, median_count=None):
    return {
        "median_count": median_count,
        "median_per_min": rate,
        "sample_count": samples,
        "load_band": band,
        "confidence": confidence,
        "data_version": "SYNTHETIC_V1",
    }


def test_waiting_is_offered_when_no_route_can_avoid_the_peak():
    departure = datetime(2026, 8, 10, 8, 0, tzinfo=MELBOURNE_TIMEZONE)
    route = _predicted_route()
    # Busy through the eight o'clock hour, quiet from nine.
    lookup = {
        ("SYNTH-A", 0, 8): _profile(200, 40, "high", "high"),
        ("SYNTH-A", 0, 9): _profile(10, 4, "low", "low"),
    }

    suggestion = suggest_calmer_departure(
        route, departure, "MEDIUM", THRESHOLDS, profile_lookup=lookup
    )

    assert suggestion["minutes_later"] == 60
    assert suggestion["predicted_peak"] == "LOW"
    assert suggestion["departure_time"].startswith("2026-08-10T09:00")
    assert "60 minutes later" in suggestion["message"]


def test_no_waiting_is_suggested_when_the_trip_already_fits_the_limit():
    departure = datetime(2026, 8, 10, 8, 0, tzinfo=MELBOURNE_TIMEZONE)
    route = _predicted_route(predicted_peak="LOW")

    assert (
        suggest_calmer_departure(
            route, departure, "MEDIUM", THRESHOLDS, profile_lookup={}
        )
        is None
    )


def _predicted_route(predicted_peak="HIGH"):
    return {
        "id": "route-1",
        "duration_minutes": 10,
        "historical_prediction_available": True,
        "predicted_peak": predicted_peak,
        "segments": [
            {
                "id": "segment-1",
                "matched_sensor_ids": ["SYNTH-A"],
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[144.9600, -37.8100], [144.9650, -37.8100]],
                },
            }
        ],
    }
