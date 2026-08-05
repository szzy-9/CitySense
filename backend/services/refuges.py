import math

from backend.data.refuges import REFUGES
from backend.repositories import list_database_refuges
from backend.services.locations import haversine_distance


def get_refuges(origin=None):
    database_refuges = list_database_refuges()
    source = "DATABASE" if database_refuges else "CURATED_PROTOTYPE"
    source_refuges = database_refuges or REFUGES
    refuges = [
        _with_distance(refuge, origin) if origin else dict(refuge)
        for refuge in source_refuges
    ]
    if origin:
        refuges.sort(key=lambda refuge: refuge["distance_meters"])
    return refuges, source


def list_refuges(origin=None):
    refuges, _source = get_refuges(origin)
    return refuges


def find_nearest_refuge(origin):
    return list_refuges(origin)[0]


def _with_distance(refuge, origin):
    distance = haversine_distance(
        [origin["lon"], origin["lat"]],
        [refuge["longitude"], refuge["latitude"]],
    )
    bearing = _bearing(
        [origin["lon"], origin["lat"]],
        [refuge["longitude"], refuge["latitude"]],
    )

    result = dict(refuge)
    result.update(
        {
            "distance_meters": round(distance),
            "bearing_degrees": round(bearing),
            "direction": _direction_label(bearing),
        }
    )
    return result


def _direction_label(bearing):
    labels = [
        "North",
        "North-east",
        "East",
        "South-east",
        "South",
        "South-west",
        "West",
        "North-west",
    ]
    index = round(bearing / 45) % 8
    return labels[index]


def _bearing(point_a, point_b):
    lon_a, lat_a = map(math.radians, point_a)
    lon_b, lat_b = map(math.radians, point_b)
    lon_change = lon_b - lon_a

    x = math.sin(lon_change) * math.cos(lat_b)
    y = (
        math.cos(lat_a) * math.sin(lat_b)
        - math.sin(lat_a) * math.cos(lat_b) * math.cos(lon_change)
    )
    return (math.degrees(math.atan2(x, y)) + 360) % 360
