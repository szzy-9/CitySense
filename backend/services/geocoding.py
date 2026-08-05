import httpx

from backend.services.locations import (
    MAX_LATITUDE,
    MAX_LONGITUDE,
    MIN_LATITUDE,
    MIN_LONGITUDE,
    is_within_supported_area,
)


AUTOCOMPLETE_URL = "https://api.heigit.org/pelias/v1/autocomplete"
MAX_AUTOCOMPLETE_RESULTS = 5


def autocomplete_locations(query, api_key, timeout=6, client=None):
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout)
    params = {
        "text": query,
        "size": MAX_AUTOCOMPLETE_RESULTS,
        "boundary.rect.min_lat": MIN_LATITUDE,
        "boundary.rect.max_lat": MAX_LATITUDE,
        "boundary.rect.min_lon": MIN_LONGITUDE,
        "boundary.rect.max_lon": MAX_LONGITUDE,
        "boundary.country": "AU",
        "focus.point.lat": -37.8136,
        "focus.point.lon": 144.9631,
    }

    try:
        response = http_client.get(
            AUTOCOMPLETE_URL,
            params=params,
            headers={"Authorization": api_key},
        )
        response.raise_for_status()
        features = response.json().get("features", [])
    finally:
        if owns_client:
            http_client.close()

    results = []
    for index, feature in enumerate(features):
        result = _read_feature(feature, index)
        if result:
            results.append(result)
        if len(results) == MAX_AUTOCOMPLETE_RESULTS:
            break
    return results


def _read_feature(feature, index):
    geometry = feature.get("geometry", {})
    coordinates = geometry.get("coordinates")
    properties = feature.get("properties", {})
    if (
        geometry.get("type") != "Point"
        or not isinstance(coordinates, list)
        or len(coordinates) < 2
    ):
        return None

    try:
        lon = float(coordinates[0])
        lat = float(coordinates[1])
    except (TypeError, ValueError):
        return None
    if not is_within_supported_area(lat, lon):
        return None

    label = properties.get("label") or properties.get("name")
    if not isinstance(label, str):
        return None
    label = " ".join(label.split())[:160]
    if not label:
        return None

    result_id = properties.get("gid") or properties.get("id") or f"result-{index + 1}"
    return {
        "id": str(result_id)[:200],
        "label": label,
        "lat": lat,
        "lon": lon,
        "source": "heigit_pelias",
    }
