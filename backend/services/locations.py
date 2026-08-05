import math


MIN_LATITUDE = -37.86
MAX_LATITUDE = -37.77
MIN_LONGITUDE = 144.92
MAX_LONGITUDE = 145.02
MAX_LOCATION_LABEL_LENGTH = 160
MAX_ROUTE_COORDINATES = 500
ALLOWED_LOCATION_SOURCES = {
    "autocomplete",
    "heigit_pelias",
    "current_location",
    "reroute",
}


def validate_location(value, field_name="Location"):
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a confirmed location.")

    label = value.get("label")
    source = value.get("source")
    if not isinstance(label, str):
        raise ValueError(f"{field_name} must include a valid address label.")

    label = " ".join(label.split())
    if not label or len(label) > MAX_LOCATION_LABEL_LENGTH:
        raise ValueError(f"{field_name} must include a valid address label.")
    if source not in ALLOWED_LOCATION_SOURCES:
        raise ValueError(f"{field_name} must be selected or confirmed first.")

    lat = _coordinate(value.get("lat"), "latitude")
    lon = _coordinate(value.get("lon"), "longitude")
    if not is_within_supported_area(lat, lon):
        raise ValueError(f"{field_name} is outside the supported Melbourne area.")

    return {
        "label": label,
        "lat": lat,
        "lon": lon,
        "source": source,
    }


def validate_search_query(value):
    if not isinstance(value, str):
        raise ValueError("Enter an address to search.")

    query = " ".join(value.split())
    if len(query) < 2 or len(query) > 120:
        raise ValueError("Address search must be between 2 and 120 characters.")
    if any(ord(character) < 32 for character in query):
        raise ValueError("Address search contains unsupported characters.")
    return query


def is_within_supported_area(lat, lon):
    return (
        MIN_LATITUDE <= lat <= MAX_LATITUDE
        and MIN_LONGITUDE <= lon <= MAX_LONGITUDE
    )


def locations_are_same(start, end):
    return haversine_distance(
        [start["lon"], start["lat"]],
        [end["lon"], end["lat"]],
    ) < 5


def validate_route_coordinates(value):
    if not isinstance(value, list):
        raise ValueError("Remaining route geometry must be a coordinate list.")
    if len(value) < 2 or len(value) > MAX_ROUTE_COORDINATES:
        raise ValueError(
            f"Remaining route geometry must contain 2 to {MAX_ROUTE_COORDINATES} points."
        )

    coordinates = []
    for point in value:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("Each route point must contain longitude and latitude.")
        lon = _coordinate(point[0], "longitude")
        lat = _coordinate(point[1], "latitude")
        if not is_within_supported_area(lat, lon):
            raise ValueError("Route geometry is outside the supported Melbourne area.")
        coordinates.append([lon, lat])
    return coordinates


def _coordinate(value, name):
    if isinstance(value, bool):
        raise ValueError(f"Location {name} must be a number.")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Location {name} must be a number.") from error
    if not math.isfinite(number):
        raise ValueError(f"Location {name} must be a finite number.")
    return number


def haversine_distance(point_a, point_b):
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
