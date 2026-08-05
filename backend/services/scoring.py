import math
from datetime import datetime, timezone


LOW = "LOW"
MODERATE = "MODERATE"
HIGH = "HIGH"
NO_DATA = "NO_DATA"

LOAD_RANK = {
    LOW: 1,
    MODERATE: 2,
    HIGH: 3,
}

MAX_ROUTE_SEGMENTS = 8
SENSOR_MATCH_DISTANCE_METERS = 180
FRESH_DATA_MINUTES = 45
MIN_HIGH_CONFIDENCE_SENSORS = 3
MIN_HIGH_CONFIDENCE_COVERAGE = 0.60
MIN_CLASSIFICATION_COVERAGE = 0.25

TOLERANCE_MAX_RANK = {
    "LOW": LOAD_RANK[LOW],
    "MEDIUM": LOAD_RANK[MODERATE],
    "HIGH": LOAD_RANK[HIGH],
}


def score_routes(
    routes,
    pedestrian_snapshot,
    route_source="live",
    crowd_tolerance="MEDIUM",
):
    if crowd_tolerance not in TOLERANCE_MAX_RANK:
        raise ValueError("Unsupported crowd tolerance")

    scored_routes = [
        _score_route(
            route,
            pedestrian_snapshot,
            route_source,
            crowd_tolerance,
        )
        for route in routes
    ]

    fastest = min(scored_routes, key=lambda route: route["duration_minutes"])
    calmest = select_calmest_route(scored_routes)
    recommended, congestion_avoidable, recommendation_reason = (
        select_recommended_route(scored_routes)
    )

    fastest["roles"].append("Fastest")
    calmest["roles"].append("Calmest")
    recommended["roles"].append("Recommended")

    for route in scored_routes:
        route["recommended"] = route["id"] == recommended["id"]
        route["congestion_avoidable"] = congestion_avoidable
        route["recommendation_reason"] = _recommendation_reason(
            route,
            recommended,
            recommendation_reason,
        )

    return scored_routes, fastest["id"], calmest["id"], recommended["id"]


def worst_load_level(levels):
    reliable_levels = [level for level in levels if level in LOAD_RANK]
    if not reliable_levels:
        return NO_DATA

    return max(reliable_levels, key=lambda level: LOAD_RANK[level])


def select_calmest_route(routes):
    def calmest_key(route):
        level_rank = LOAD_RANK.get(route["sensory_level"], 4)
        average_load = route.get("average_load")
        if average_load is None:
            average_load = math.inf

        return (
            level_rank,
            -route.get("coverage", 0),
            average_load,
            route["duration_minutes"],
        )

    return min(routes, key=calmest_key)


def select_recommended_route(routes):
    within_threshold = [
        route
        for route in routes
        if route["sensory_indicator"] == LOW
    ]
    if within_threshold:
        return (
            select_calmest_route(within_threshold),
            True,
            "Recommended because its observed peak is within your selected crowd limit.",
        )

    observed_above_threshold = [
        route
        for route in routes
        if route["sensory_indicator"] == HIGH
    ]
    if observed_above_threshold:
        if len(observed_above_threshold) == len(routes):
            reason = (
                "All available walking routes contain at least one segment above "
                "your selected crowd limit. This route has the lowest observed peak."
            )
        else:
            reason = (
                "No below-threshold route could be confirmed because some route data "
                "is unavailable. This route has the lowest observed peak."
            )
        return select_calmest_route(observed_above_threshold), False, reason

    return (
        select_calmest_route(routes),
        False,
        "Crowd data is insufficient to confirm that congestion can be avoided.",
    )


def load_level_for_count(count):
    if count is None:
        return NO_DATA
    if count <= 200:
        return LOW
    if count <= 500:
        return MODERATE
    return HIGH


def calculate_confidence(
    route_source,
    pedestrian_source,
    updated_at,
    sensor_count,
    coverage,
    sensory_level,
    now=None,
):
    reasons = confidence_reasons(
        route_source=route_source,
        pedestrian_source=pedestrian_source,
        updated_at=updated_at,
        sensor_count=sensor_count,
        coverage=coverage,
        sensory_level=sensory_level,
        now=now,
    )
    if reasons:
        return "LOW", reasons[0]

    return (
        "HIGH",
        f"Live data from {sensor_count} nearby sensors with "
        f"{round(coverage * 100)}% coverage.",
    )


def confidence_reasons(
    route_source,
    pedestrian_source,
    updated_at,
    sensor_count,
    coverage,
    sensory_level,
    now=None,
):
    reasons = []
    if route_source != "live":
        reasons.append("Prototype route; confidence is low.")
    if pedestrian_source != "live":
        reasons.append("Pedestrian data is fallback data.")
    if sensory_level == NO_DATA:
        reasons.append("No reliable crowd data near this route.")
    if not _is_fresh(updated_at, now):
        reasons.append("Pedestrian data may be out of date.")
    if sensor_count < MIN_HIGH_CONFIDENCE_SENSORS:
        reasons.append("Too few nearby sensors for high confidence.")
    if coverage < MIN_HIGH_CONFIDENCE_COVERAGE:
        reasons.append("Limited sensor coverage.")
    return reasons


def _score_route(
    route,
    pedestrian_snapshot,
    route_source,
    crowd_tolerance,
):
    segment_records = _build_route_segments(
        route["geometry"]["coordinates"],
        pedestrian_snapshot["sensors"],
    )
    matched_sensors = {}

    for segment in segment_records:
        for sensor in segment.pop("_matched_sensors"):
            matched_sensors[str(sensor["id"])] = sensor

    public_sensors = [
        _public_sensor(sensor)
        for sensor in matched_sensors.values()
    ]
    public_sensors.sort(key=lambda sensor: sensor["name"])

    sensory_level = worst_load_level(
        [segment["sensory_level"] for segment in segment_records]
    )
    observed_segments = sum(
        segment["sensory_level"] != NO_DATA
        for segment in segment_records
    )
    coverage = (
        round(observed_segments / len(segment_records), 2)
        if segment_records
        else 0
    )

    counts = [sensor["count"] for sensor in public_sensors]
    average_load = round(sum(counts) / len(counts)) if counts else None
    peak_sensor = max(public_sensors, key=lambda sensor: sensor["count"], default=None)
    peak_count = peak_sensor["count"] if peak_sensor else None
    peak_location = (
        peak_sensor["name"]
        if peak_sensor and pedestrian_snapshot["source"] == "live"
        else None
    )

    confidence, confidence_explanation = calculate_confidence(
        route_source=route_source,
        pedestrian_source=pedestrian_snapshot["source"],
        updated_at=pedestrian_snapshot["updated_at"],
        sensor_count=len(public_sensors),
        coverage=coverage,
        sensory_level=sensory_level,
    )
    reasons = confidence_reasons(
        route_source=route_source,
        pedestrian_source=pedestrian_snapshot["source"],
        updated_at=pedestrian_snapshot["updated_at"],
        sensor_count=len(public_sensors),
        coverage=coverage,
        sensory_level=sensory_level,
    )
    sensory_indicator = route_sensory_indicator(
        peak_load=sensory_level,
        coverage=coverage,
        route_source=route_source,
        pedestrian_source=pedestrian_snapshot["source"],
        crowd_tolerance=crowd_tolerance,
        updated_at=pedestrian_snapshot.get("updated_at"),
    )

    scored_route = dict(route)
    scored_route.pop("simulated_crowd_score", None)
    scored_route.update(
        {
            "roles": [],
            "segments": segment_records,
            "sensory_level": sensory_level,
            "peak_load": sensory_level,
            "sensory_indicator": sensory_indicator,
            "crowd_label": _level_label(sensory_level),
            "crowd_score": peak_count,
            "sensor_count": len(public_sensors),
            "matched_sensor_count": len(public_sensors),
            "matched_sensors": public_sensors,
            "coverage": coverage,
            "average_load": average_load,
            "peak_location": peak_location,
            "confidence": confidence,
            "confidence_explanation": confidence_explanation,
            "confidence_reasons": reasons,
            "data_status": _route_data_status(
                route_source,
                pedestrian_snapshot["source"],
                sensory_level,
            ),
            "last_updated": pedestrian_snapshot["updated_at"],
            "route_source": route_source,
            "pedestrian_source": pedestrian_snapshot["source"],
            "explanation": _route_explanation(
                sensory_level,
                peak_location,
                segment_records,
            ),
        }
    )
    return scored_route


def route_sensory_indicator(
    peak_load,
    coverage,
    route_source,
    pedestrian_source,
    crowd_tolerance,
    updated_at=None,
    now=None,
):
    if (
        peak_load == NO_DATA
        or coverage < MIN_CLASSIFICATION_COVERAGE
        or route_source != "live"
        or pedestrian_source != "live"
        or not _is_fresh(updated_at, now)
    ):
        return NO_DATA

    if LOAD_RANK[peak_load] <= TOLERANCE_MAX_RANK[crowd_tolerance]:
        return LOW
    return HIGH


def monitor_route(
    coordinates,
    pedestrian_snapshot,
    crowd_tolerance,
    now=None,
):
    if crowd_tolerance not in TOLERANCE_MAX_RANK:
        raise ValueError("Unsupported crowd tolerance")

    if (
        pedestrian_snapshot["source"] != "live"
        or not _is_fresh(pedestrian_snapshot.get("updated_at"), now)
    ):
        return {
            "breached": False,
            "upcoming_peak": NO_DATA,
            "affected_segment_index": None,
            "message": "Recent reliable crowd monitoring data is unavailable.",
        }

    segments = _build_route_segments(
        coordinates,
        pedestrian_snapshot["sensors"],
    )
    levels = [segment["sensory_level"] for segment in segments]
    upcoming_peak = worst_load_level(levels)
    threshold_rank = TOLERANCE_MAX_RANK[crowd_tolerance]
    affected_segment_index = next(
        (
            index
            for index, level in enumerate(levels)
            if level in LOAD_RANK and LOAD_RANK[level] > threshold_rank
        ),
        None,
    )
    breached = affected_segment_index is not None

    if breached:
        message = (
            f"{_level_label(upcoming_peak)} crowd levels were detected ahead."
        )
    elif upcoming_peak == NO_DATA:
        message = "No reliable crowd data is available for the route ahead."
    else:
        message = "No crowd level above your selected limit was detected ahead."

    return {
        "breached": breached,
        "upcoming_peak": upcoming_peak,
        "affected_segment_index": affected_segment_index,
        "message": message,
    }


def _recommendation_reason(route, recommended, recommended_reason):
    if route["id"] == recommended["id"]:
        return recommended_reason
    if route["sensory_indicator"] == HIGH:
        return "Not recommended for your selected crowd threshold."
    if route["sensory_indicator"] == NO_DATA:
        return (
            "Not recommended by default because reliable crowd coverage is insufficient."
        )
    return "Another route has a lower observed peak or stronger data coverage."


def _build_route_segments(coordinates, sensors):
    coordinate_groups = _split_coordinates(coordinates)
    segments = []

    for index, segment_coordinates in enumerate(coordinate_groups, start=1):
        matched = _match_sensors(segment_coordinates, sensors)
        peak_sensor = max(matched, key=lambda sensor: sensor["count"], default=None)
        peak_count = peak_sensor["count"] if peak_sensor else None

        segments.append(
            {
                "id": f"segment-{index}",
                "geometry": {
                    "type": "LineString",
                    "coordinates": segment_coordinates,
                },
                "sensory_level": load_level_for_count(peak_count),
                "sensor_count": len(matched),
                "peak_count": peak_count,
                "_matched_sensors": matched,
            }
        )

    return segments


def _split_coordinates(coordinates):
    if len(coordinates) < 2:
        return []

    edge_count = len(coordinates) - 1
    segment_count = min(MAX_ROUTE_SEGMENTS, edge_count)
    groups = []

    for index in range(segment_count):
        start_edge = math.floor(index * edge_count / segment_count)
        end_edge = math.floor((index + 1) * edge_count / segment_count)
        end_edge = max(end_edge, start_edge + 1)
        groups.append(coordinates[start_edge : end_edge + 1])

    return groups


def _match_sensors(coordinates, sensors):
    sample_points = _sample_route(coordinates)
    matched = []

    for sensor in sensors:
        sensor_point = [sensor["lon"], sensor["lat"]]
        nearest_distance = min(
            _haversine(sensor_point, route_point)
            for route_point in sample_points
        )
        if nearest_distance <= SENSOR_MATCH_DISTANCE_METERS:
            matched.append(sensor)

    return matched


def _sample_route(coordinates):
    points = []

    for index in range(len(coordinates) - 1):
        start = coordinates[index]
        end = coordinates[index + 1]

        for step in range(6):
            amount = step / 5
            points.append(
                [
                    start[0] + (end[0] - start[0]) * amount,
                    start[1] + (end[1] - start[1]) * amount,
                ]
            )

    points.append(coordinates[-1])
    return points


def _public_sensor(sensor):
    return {
        "id": str(sensor["id"]),
        "name": sensor["name"],
        "lat": sensor["lat"],
        "lon": sensor["lon"],
        "count": sensor["count"],
        "sensory_level": load_level_for_count(sensor["count"]),
    }


def _route_data_status(route_source, pedestrian_source, sensory_level):
    if route_source != "live":
        return "PROTOTYPE"
    if pedestrian_source != "live":
        return "FALLBACK"
    if sensory_level == NO_DATA:
        return "NO_DATA"
    return "LIVE"


def _route_explanation(sensory_level, peak_location, segments):
    if sensory_level == NO_DATA:
        return "No reliable crowd data for this route."

    level = _level_label(sensory_level)
    if peak_location:
        return f"Peaks at {level} near {peak_location}."

    has_no_data = any(
        segment["sensory_level"] == NO_DATA
        for segment in segments
    )
    if has_no_data:
        return f"Observed peak is {level}; part of the route has no data."
    return f"No observed segment is above {level}."


def _level_label(level):
    labels = {
        LOW: "Low",
        MODERATE: "Moderate",
        HIGH: "High",
        NO_DATA: "No Data",
    }
    return labels[level]


def _is_fresh(updated_at, now=None):
    if not updated_at:
        return False

    try:
        updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False

    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)

    current_time = now or datetime.now(timezone.utc)
    age_minutes = (current_time - updated).total_seconds() / 60
    return -5 <= age_minutes <= FRESH_DATA_MINUTES


def _haversine(point_a, point_b):
    lon_a, lat_a = point_a
    lon_b, lat_b = point_b
    earth_radius = 6_371_000

    lat_change = math.radians(lat_b - lat_a)
    lon_change = math.radians(lon_b - lon_a)
    value = (
        math.sin(lat_change / 2) ** 2
        + math.cos(math.radians(lat_a))
        * math.cos(math.radians(lat_b))
        * math.sin(lon_change / 2) ** 2
    )
    return earth_radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))
