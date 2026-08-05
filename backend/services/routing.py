import math
import logging

import httpx


ORS_URL = "https://api.openrouteservice.org/v2/directions/foot-walking/geojson"
logger = logging.getLogger(__name__)


def get_walking_routes(start, end, api_key, timeout=6, client=None):
    if api_key:
        try:
            routes = _request_live_routes(start, end, api_key, timeout, client)
            if len(routes) >= 2:
                return routes[:2], "live", "OpenRouteService walking routes"
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            logger.warning(
                "OpenRouteService is unavailable; using simulated routes (%s)",
                type(error).__name__,
            )

    routes = _build_fallback_routes(start, end)
    return routes, "fallback", "Two locally simulated walking routes"


def _request_live_routes(start, end, api_key, timeout, client=None):
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout)
    payload = {
        "coordinates": [
            [start["lon"], start["lat"]],
            [end["lon"], end["lat"]],
        ],
        "instructions": False,
        "alternative_routes": {
            "target_count": 2,
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
        features = response.json().get("features", [])
    finally:
        if owns_client:
            http_client.close()

    routes = []
    for index, feature in enumerate(features):
        summary = feature.get("properties", {}).get("summary", {})
        geometry = feature.get("geometry", {})

        if geometry.get("type") != "LineString":
            continue

        routes.append(
            {
                "id": f"route-{index + 1}",
                "geometry": geometry,
                "distance_meters": round(float(summary["distance"])),
                "duration_minutes": round(float(summary["duration"]) / 60, 1),
            }
        )

    return routes


def _build_fallback_routes(start, end):
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
            "simulated_crowd_score": 540,
        },
        {
            "id": "route-2",
            "geometry": {"type": "LineString", "coordinates": calm_coordinates},
            "distance_meters": round(calm_distance),
            "duration_minutes": round(calm_distance / 76, 1),
            "simulated_crowd_score": 165,
        },
    ]


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
