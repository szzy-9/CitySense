import logging
import math

import httpx


ORS_URL = (
    "https://api.heigit.org/openrouteservice/v2/directions/"
    "foot-walking/geojson"
)
logger = logging.getLogger(__name__)

# Two routes is the minimum that makes a comparison, and three is as many as a
# phone screen can present without the choice itself becoming the burden.
MAX_ROUTES = 3


# Why live routing failed matters in the logs, not on screen: every cause means
# the same thing to the person walking, and naming our internals ("authentication
# failed") tells them nothing they can act on.
FALLBACK_REASON = (
    "Live routing is unavailable, so these are example routes rather than real ones."
)


def get_walking_routes(start, end, api_key, timeout=6, client=None):
    fallback_reason = FALLBACK_REASON

    if api_key:
        try:
            routes = _request_live_routes(start, end, api_key, timeout, client)
            if len(routes) >= 2:
                return routes[:MAX_ROUTES], "live", "OpenRouteService walking routes"
            logger.warning("OpenRouteService fallback category=insufficient_routes")
        except httpx.TimeoutException:
            logger.warning("OpenRouteService fallback category=timeout")
        except httpx.HTTPStatusError as error:
            category = (
                "authentication"
                if error.response.status_code in {401, 403}
                else "http_status"
            )
            logger.warning("OpenRouteService fallback category=%s", category)
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            logger.warning("OpenRouteService fallback category=invalid_response")

    routes = _build_fallback_routes(start, end, fallback_reason)
    return routes, "fallback", fallback_reason


def _request_live_routes(start, end, api_key, timeout, client=None):
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout)
    payload = {
        "coordinates": [
            [start["lon"], start["lat"]],
            [end["lon"], end["lat"]],
        ],
        "instructions": True,
        "alternative_routes": {
            "target_count": MAX_ROUTES,
            "weight_factor": 1.6,
            "share_factor": 0.6,
        },
    }

    try:
        response = http_client.post(
            ORS_URL,
            headers={"Authorization": api_key},
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("Invalid route response")
        features = body.get("features", [])
        if not isinstance(features, list):
            raise ValueError("Invalid route features")
    finally:
        if owns_client:
            http_client.close()

    routes = []
    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties", {})
        summary = properties.get("summary", {})
        geometry = feature.get("geometry", {})

        coordinates = geometry.get("coordinates")
        if (
            geometry.get("type") != "LineString"
            or not isinstance(coordinates, list)
            or len(coordinates) < 2
        ):
            continue

        distance = float(summary["distance"])
        duration = float(summary["duration"])
        if not math.isfinite(distance) or not math.isfinite(duration):
            continue
        if distance <= 0 or duration <= 0:
            continue

        routes.append(
            {
                "id": f"route-{index + 1}",
                "geometry": geometry,
                "distance_meters": round(distance),
                "duration_minutes": round(duration / 60, 1),
                "steps": _read_steps(properties, coordinates),
                "source": "LIVE",
                "fallback_reason": None,
            }
        )

    return routes


def _build_fallback_routes(start, end, fallback_reason):
    start_point = [start["lon"], start["lat"]]
    end_point = [end["lon"], end["lat"]]
    lon_change = end["lon"] - start["lon"]
    lat_change = end["lat"] - start["lat"]
    line_length = math.sqrt(lon_change**2 + lat_change**2) or 1

    offset_lon = -lat_change / line_length * 0.0012
    offset_lat = lon_change / line_length * 0.0012

    fastest_coordinates = [
        start_point,
        _between(start_point, end_point, 0.5),
        end_point,
    ]
    calm_coordinates = [
        start_point,
        _offset(_between(start_point, end_point, 0.30), offset_lon, offset_lat),
        _offset(_between(start_point, end_point, 0.70), offset_lon, offset_lat),
        end_point,
    ]

    fastest_distance = _line_distance(fastest_coordinates)
    calm_distance = _line_distance(calm_coordinates)

    return [
        {
            "id": "route-1",
            "geometry": {"type": "LineString", "coordinates": fastest_coordinates},
            "distance_meters": round(fastest_distance),
            "duration_minutes": round(fastest_distance / 80, 1),
            "steps": [],
            "source": "PROTOTYPE",
            "fallback_reason": fallback_reason,
        },
        {
            "id": "route-2",
            "geometry": {"type": "LineString", "coordinates": calm_coordinates},
            "distance_meters": round(calm_distance),
            "duration_minutes": round(calm_distance / 76, 1),
            "steps": [],
            "source": "PROTOTYPE",
            "fallback_reason": fallback_reason,
        },
    ]


def _read_steps(properties, coordinates):
    direction_segments = properties.get("segments", [])
    if not isinstance(direction_segments, list):
        return []

    steps = []
    for direction_segment in direction_segments:
        if not isinstance(direction_segment, dict):
            continue
        for step in direction_segment.get("steps", []):
            normalized = _read_step(step, coordinates)
            if normalized:
                normalized["index"] = len(steps)
                steps.append(normalized)
    return steps


def _read_step(step, coordinates):
    if not isinstance(step, dict):
        return None

    instruction = step.get("instruction")
    way_points = step.get("way_points")
    if (
        not isinstance(instruction, str)
        or not instruction.strip()
        or not isinstance(way_points, list)
        or len(way_points) != 2
    ):
        return None

    try:
        start_index = int(way_points[0])
        end_index = int(way_points[1])
        distance = float(step.get("distance", 0))
        duration = float(step.get("duration", 0))
    except (TypeError, ValueError):
        return None

    if (
        start_index < 0
        or end_index < start_index
        or end_index >= len(coordinates)
        or not math.isfinite(distance)
        or not math.isfinite(duration)
    ):
        return None

    return {
        "instruction": " ".join(instruction.split())[:240],
        "distance_meters": round(max(0, distance)),
        "duration_seconds": round(max(0, duration)),
        "way_points": [start_index, end_index],
    }


def _between(start, end, amount):
    return [
        start[0] + (end[0] - start[0]) * amount,
        start[1] + (end[1] - start[1]) * amount,
    ]


def _offset(point, lon_amount, lat_amount):
    return [point[0] + lon_amount, point[1] + lat_amount]


def _line_distance(coordinates):
    distance = 0
    for index in range(len(coordinates) - 1):
        distance += _haversine(coordinates[index], coordinates[index + 1])
    return distance


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
