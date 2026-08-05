import math


def score_routes(routes, pedestrian_snapshot):
    scored_routes = []

    for route in routes:
        scored_route = dict(route)
        crowd_score, sensor_count = _crowd_score(
            route,
            pedestrian_snapshot["sensors"],
        )
        scored_route.pop("simulated_crowd_score", None)
        scored_route["crowd_score"] = crowd_score
        scored_route["crowd_label"] = _crowd_label(crowd_score)
        scored_route["matched_sensor_count"] = sensor_count
        scored_route["roles"] = []
        scored_routes.append(scored_route)

    fastest = min(scored_routes, key=lambda route: route["duration_minutes"])
    routes_with_data = [route for route in scored_routes if route["crowd_score"] is not None]
    calmest = min(
        routes_with_data or scored_routes,
        key=lambda route: (
            route["crowd_score"] is None,
            route["crowd_score"] or 0,
            route["duration_minutes"],
        ),
    )

    fastest["roles"].append("Fastest")
    calmest["roles"].append("Calmest")

    return scored_routes, fastest["id"], calmest["id"]


def _crowd_score(route, sensors):
    simulated_score = route.get("simulated_crowd_score")
    if simulated_score is not None:
        simulated_sensor_count = 5 if simulated_score > 300 else 3
        return simulated_score, simulated_sensor_count

    sample_points = _sample_route(route["geometry"]["coordinates"])
    nearby_counts = []

    for sensor in sensors:
        sensor_point = [sensor["lon"], sensor["lat"]]
        nearest_distance = min(
            _haversine(sensor_point, route_point) for route_point in sample_points
        )
        if nearest_distance <= 180:
            nearby_counts.append(sensor["count"])

    if not nearby_counts:
        return None, 0

    average = sum(nearby_counts) / len(nearby_counts)
    return round(average), len(nearby_counts)


def _sample_route(coordinates):
    points = []

    for index in range(len(coordinates) - 1):
        start = coordinates[index]
        end = coordinates[index + 1]

        for step in range(11):
            amount = step / 10
            points.append(
                [
                    start[0] + (end[0] - start[0]) * amount,
                    start[1] + (end[1] - start[1]) * amount,
                ]
            )

    points.append(coordinates[-1])
    return points


def _crowd_label(score):
    if score is None:
        return "No nearby data"
    if score <= 200:
        return "Quieter"
    if score <= 500:
        return "Moderate"
    return "Busy"


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

