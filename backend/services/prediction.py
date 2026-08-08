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
# The imported profiles are built from the counts-per-hour dataset, so a
# median_count is people in a whole hour. Live readings, and therefore the load
# bands, are people per minute. Banding an hourly total against a per-minute
# scale reported the CBD as High at three in the morning.
MINUTES_PER_HOUR = 60
CONFIDENCE_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
ROUTE_UNAVAILABLE = {
    "historical_prediction_available": False,
    "predicted_peak": NO_DATA,
    "predicted_count": None,
    "prediction_confidence": "LOW",
    "prediction_basis": None,
    # Stated from the reader's side: we have no past pattern for these sensors at
    # this time of day. Naming an internal load step here has misreported the
    # cause before, because a populated table can still miss this weekday/hour.
    "prediction_unavailable_reason": (
        "We have no past pattern for this route at this time of day."
    ),
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


def per_minute_rate(hourly_count):
    """An hourly profile total expressed in the unit the load bands are written in.

    This is an average minute across the hour, so it reads calmer than a live
    spot reading of the busiest minute. A forecast says what the hour is
    usually like; it does not claim to name its worst thirty seconds.
    """
    if hourly_count is None:
        return None
    return hourly_count / MINUTES_PER_HOUR


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
                "No past pattern for this stretch at this time of day."
            ),
        }

    predictions = [
        {
            "count": per_minute_rate(profile["median_count"]),
            "band": load_level_for_count(per_minute_rate(profile["median_count"])),
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
        "prediction_basis": "Based on the same weekday and hour in past weeks",
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
        "prediction_basis": "Based on the same weekday and hour in past weeks",
        "prediction_coverage": round(prediction_coverage, 2),
        "prediction_unavailable_reason": (
            "We only have past patterns for part of this route."
            if limited_coverage
            else
            "This is an example route, so the outlook is less certain."
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
            f"Likely {first['predicted_band'].lower()} in about "
            f"{round(first['prediction_lead_minutes'])} minutes, based on past weeks."
        ),
        "reroute_available": True,
    }


# Far enough ahead to clear a commuter peak, in steps small enough to be worth
# acting on. Every candidate is answered from the imported profiles already in
# memory, so the whole scan costs one database read.
DEPARTURE_OFFSETS_MINUTES = (15, 30, 45, 60, 75, 90)


def suggest_calmer_departure(
    route,
    departure_time,
    crowd_tolerance,
    thresholds,
    profile_lookup=None,
):
    """The soonest later departure whose predicted peak sits within tolerance.

    Rerouting cannot help when every path crosses the same busy corner. Waiting
    can, and for a commuter who can flex their start it is usually the only
    lever that removes a High rather than relabelling it.
    """
    threshold_rank = TOLERANCE_MAX_RANK[crowd_tolerance]
    if not route.get("historical_prediction_available"):
        return None
    if LOAD_RANK.get(route.get("predicted_peak"), 4) <= threshold_rank:
        return None

    segments = route.get("segments", [])
    sensor_ids = {
        sensor_id
        for segment in segments
        for sensor_id in segment.get("matched_sensor_ids", [])
    }
    if not sensor_ids:
        return None

    leads = _segment_lead_minutes(route)
    candidates = [
        departure_time + timedelta(minutes=offset)
        for offset in DEPARTURE_OFFSETS_MINUTES
    ]
    arrival_times = [
        candidate + timedelta(minutes=lead)
        for candidate in candidates
        for lead in leads
    ]
    if profile_lookup is None:
        profile_lookup = get_historical_profiles_for_times(sensor_ids, arrival_times)

    for offset, candidate in zip(DEPARTURE_OFFSETS_MINUTES, candidates):
        peak = _predicted_peak_at(segments, leads, candidate, profile_lookup)
        if peak is None or peak == NO_DATA:
            continue
        if LOAD_RANK.get(peak, 4) <= threshold_rank:
            return {
                "departure_time": candidate.isoformat(),
                "minutes_later": offset,
                "predicted_peak": peak,
                "message": (
                    f"Leaving {offset} minutes later drops the busiest point to "
                    f"{peak.lower()}, based on the same weekday and hour in past weeks."
                ),
            }
    return None


def _predicted_peak_at(segments, leads, departure_time, lookup):
    bands = []
    for segment, lead in zip(segments, leads):
        arrival = departure_time + timedelta(minutes=lead)
        profiles = [
            lookup.get((sensor_id, arrival.weekday(), arrival.hour))
            for sensor_id in segment.get("matched_sensor_ids", [])
        ]
        counts = [
            per_minute_rate(profile["median_count"]) for profile in profiles if profile
        ]
        if counts:
            bands.append(load_level_for_count(max(counts)))
    if not bands:
        return None
    return worst_load_level(bands)


def _segment_lead_minutes(route):
    segments = route.get("segments", [])
    lengths = [
        _geometry_length(segment["geometry"]["coordinates"]) for segment in segments
    ]
    total_length = sum(lengths)
    leads = []
    elapsed_fraction = 0.0
    for segment_length in lengths:
        if total_length > 0:
            elapsed_fraction += segment_length / total_length
        else:
            elapsed_fraction += 1 / max(len(segments), 1)
        leads.append(route["duration_minutes"] * elapsed_fraction)
    return leads


def _geometry_length(coordinates):
    return sum(
        haversine_distance(coordinates[index], coordinates[index + 1])
        for index in range(len(coordinates) - 1)
    )
