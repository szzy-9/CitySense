"""Explainable historical baseline predictions for already-generated routes."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from backend.repositories import get_historical_profiles_for_times
from backend.services.locations import haversine_distance
from backend.services.scoring import (
    LOAD_RANK,
    NO_DATA,
    TOLERANCE_MAX_RANK,
    load_level_for_count,
    worst_load_level,
)


MELBOURNE_TIMEZONE = ZoneInfo("Australia/Melbourne")
CONFIDENCE_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
ROUTE_UNAVAILABLE = {
    "historical_prediction_available": False,
    "predicted_peak": NO_DATA,
    "predicted_count": None,
    "prediction_confidence": "LOW",
    "prediction_basis": None,
    "prediction_unavailable_reason": "Historical profile data has not been loaded.",
    "prediction_alert": None,
}


def parse_departure_time(value, now=None):
    """Return a timezone-aware departure time and whether a default was used."""
    if value in (None, ""):
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(MELBOURNE_TIMEZONE), True
    if not isinstance(value, str):
        raise ValueError("Departure time must be an ISO 8601 timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Departure time must be an ISO 8601 timestamp.") from None
    if parsed.tzinfo is None:
        raise ValueError("Departure time must include a timezone offset.")
    return parsed.astimezone(MELBOURNE_TIMEZONE), False


def prediction_confidence(profile, thresholds):
    """Classify an imported profile by sample size and coefficient of variation."""
    sample_count = profile.get("sample_count") or 0
    mean_count = profile.get("mean_count") or 0
    std_count = profile.get("std_dev") or 0
    if mean_count == 0:
        coefficient = 0 if std_count == 0 else math.inf
    else:
        coefficient = std_count / mean_count

    if (
        sample_count >= thresholds["high_min_samples"]
        and coefficient <= thresholds["high_max_cv"]
    ):
        return "HIGH"
    if (
        sample_count >= thresholds["medium_min_samples"]
        and coefficient <= thresholds["medium_max_cv"]
    ):
        return "MEDIUM"
    return "LOW"


def add_historical_predictions(
    routes,
    departure_time,
    crowd_tolerance,
    thresholds,
    profile_lookup=None,
):
    """Attach segment and route prediction results without changing route scoring."""
    segment_contexts = _segment_contexts(routes, departure_time)
    sensor_ids = {
        sensor_id
        for context in segment_contexts
        for sensor_id in context["segment"].get("matched_sensor_ids", [])
    }
    target_times = [context["arrival_time"] for context in segment_contexts]
    if profile_lookup is None:
        profile_lookup = get_historical_profiles_for_times(sensor_ids, target_times)

    for context in segment_contexts:
        segment = context["segment"]
        prediction = _segment_prediction(
            segment,
            context["arrival_time"],
            context["lead_minutes"],
            profile_lookup,
            thresholds,
        )
        segment.update(prediction)

    for route in routes:
        _summarise_route(route, crowd_tolerance, thresholds)
    return routes


def _segment_contexts(routes, departure_time):
    contexts = []
    for route in routes:
        segments = route.get("segments", [])
        lengths = [_geometry_length(segment["geometry"]["coordinates"]) for segment in segments]
        total_length = sum(lengths)
        elapsed_fraction = 0.0
        for segment, segment_length in zip(segments, lengths):
            if total_length > 0:
                elapsed_fraction += segment_length / total_length
            else:
                elapsed_fraction += 1 / max(len(segments), 1)
            lead_minutes = route["duration_minutes"] * elapsed_fraction
            arrival_time = departure_time + timedelta(minutes=lead_minutes)
            segment["estimated_arrival_time"] = arrival_time.isoformat()
            contexts.append(
                {
                    "route": route,
                    "segment": segment,
                    "arrival_time": arrival_time,
                    "lead_minutes": round(lead_minutes, 1),
                }
            )
    return contexts


def _segment_prediction(segment, arrival_time, lead_minutes, lookup, thresholds):
    profiles = [
        lookup.get((sensor_id, arrival_time.weekday(), arrival_time.hour))
        for sensor_id in segment.get("matched_sensor_ids", [])
    ]
    profiles = [profile for profile in profiles if profile]
    if not profiles:
        return {
            "historical_prediction_available": False,
            "predicted_count": None,
            "predicted_band": NO_DATA,
            "prediction_confidence": "LOW",
            "prediction_basis": None,
            "predicted_for": arrival_time.isoformat(),
            "profile_sensor_count": 0,
            "prediction_lead_minutes": lead_minutes,
            "prediction_unavailable_reason": (
                "No matching historical profile for this segment."
            ),
        }

    predictions = [
        {
            "count": profile["median_count"],
            "band": load_level_for_count(profile["median_count"]),
            "confidence": prediction_confidence(profile, thresholds),
            "sample_count": profile["sample_count"],
            "data_version": profile["data_version"],
        }
        for profile in profiles
    ]
    predicted_band = worst_load_level([item["band"] for item in predictions])
    peak_items = [item for item in predictions if item["band"] == predicted_band]
    peak_item = max(peak_items, key=lambda item: item["count"])
    confidence = min(
        (item["confidence"] for item in peak_items),
        key=lambda value: CONFIDENCE_RANK[value],
    )
    return {
        "historical_prediction_available": True,
        "predicted_band": predicted_band,
        "predicted_count": round(peak_item["count"]),
        "prediction_confidence": confidence,
        "prediction_basis": "Historical median for the same weekday and hour",
        "predicted_for": arrival_time.isoformat(),
        "profile_sensor_count": len(profiles),
        "prediction_sample_count": peak_item["sample_count"],
        "prediction_data_version": peak_item["data_version"],
        "prediction_lead_minutes": lead_minutes,
        "prediction_unavailable_reason": None,
    }


def _summarise_route(route, crowd_tolerance, thresholds):
    predictions = [
        segment
        for segment in route.get("segments", [])
    ]
    available = [
        prediction
        for prediction in predictions
        if prediction.get("historical_prediction_available")
    ]
    if not available:
        route.update(ROUTE_UNAVAILABLE)
        return

    predicted_peak = worst_load_level(
        [prediction["predicted_band"] for prediction in available]
    )
    peak_predictions = [
        prediction
        for prediction in available
        if prediction["predicted_band"] == predicted_peak
    ]
    peak_prediction = max(
        peak_predictions,
        key=lambda prediction: prediction["predicted_count"],
    )
    confidence = min(
        (prediction["prediction_confidence"] for prediction in peak_predictions),
        key=lambda value: CONFIDENCE_RANK[value],
    )
    prediction_coverage = len(available) / max(len(predictions), 1)
    limited_coverage = prediction_coverage < 1
    route.update({
        "historical_prediction_available": True,
        "predicted_peak": predicted_peak,
        "predicted_count": peak_prediction["predicted_count"],
        "prediction_confidence": "LOW" if limited_coverage else confidence,
        "prediction_basis": "Historical median for the same weekday and hour",
        "prediction_coverage": round(prediction_coverage, 2),
        "prediction_unavailable_reason": (
            "Historical profiles cover only part of this route."
            if limited_coverage
            else
            "Prototype route geometry limits prediction confidence."
            if route.get("route_source") != "live"
            else None
        ),
    })

    if route.get("route_source") != "live" or limited_coverage:
        route["prediction_confidence"] = "LOW"
        route["prediction_alert"] = None
        return

    minimum_confidence = thresholds.get("minimum_alert_confidence", "MEDIUM")
    if minimum_confidence not in {"MEDIUM", "HIGH"}:
        minimum_confidence = "MEDIUM"
    threshold_rank = TOLERANCE_MAX_RANK[crowd_tolerance]
    eligible = [
        prediction
        for prediction in available
        if 5 <= prediction["prediction_lead_minutes"] <= 60
        and LOAD_RANK.get(prediction["predicted_band"], 0) > threshold_rank
        and CONFIDENCE_RANK[prediction["prediction_confidence"]]
        >= CONFIDENCE_RANK.get(minimum_confidence, 2)
    ]
    if not eligible:
        route["prediction_alert"] = None
        return

    first = min(eligible, key=lambda prediction: prediction["prediction_lead_minutes"])
    route["prediction_alert"] = {
        "triggered": True,
        "predicted_condition": first["predicted_band"],
        "segment_index": route.get("segments", []).index(first),
        "lead_minutes": round(first["prediction_lead_minutes"]),
        "confidence": first["prediction_confidence"],
        "message": (
            f"Historical patterns suggest {first['predicted_band'].title()} crowd "
            f"levels in about {round(first['prediction_lead_minutes'])} minutes."
        ),
        "reroute_available": True,
    }


def _geometry_length(coordinates):
    return sum(
        haversine_distance(coordinates[index], coordinates[index + 1])
        for index in range(len(coordinates) - 1)
    )
