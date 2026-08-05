import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx


COUNTS_URL = (
    "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/"
    "pedestrian-counting-system-past-hour-counts-per-minute/records"
)
LOCATIONS_URL = (
    "https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/"
    "pedestrian-counting-system-sensor-locations/records"
)
FALLBACK_FILE = Path(__file__).resolve().parents[1] / "data" / "pedestrian_fallback.json"
logger = logging.getLogger(__name__)
LIVE_CACHE_SECONDS = 60
_live_cache = {"snapshot": None, "stored_at": 0.0}


def get_pedestrian_snapshot(use_live=True, timeout=6, client=None):
    if use_live:
        if client is None and _cache_is_current():
            snapshot = dict(_live_cache["snapshot"])
            snapshot["message"] = "Cached live City of Melbourne pedestrian data"
            snapshot["cache_status"] = "cached"
            return snapshot
        try:
            snapshot = _read_live_data(timeout, client)
            snapshot["cache_status"] = "live"
            if client is None:
                _live_cache["snapshot"] = snapshot
                _live_cache["stored_at"] = time.monotonic()
            return snapshot
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            logger.warning(
                "City pedestrian data is unavailable; using fallback data (%s)",
                type(error).__name__,
            )

    return _read_fallback_data()


def _cache_is_current():
    return (
        _live_cache["snapshot"] is not None
        and time.monotonic() - _live_cache["stored_at"] <= LIVE_CACHE_SECONDS
    )


def _read_live_data(timeout, client=None):
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout)

    try:
        count_params = {
            "select": (
                "location_id, max(sensing_datetime) as sensing_datetime, "
                "sum(total_of_directions) as total_count"
            ),
            "group_by": "location_id",
            "limit": 100,
        }
        count_response = http_client.get(COUNTS_URL, params=count_params)
        count_response.raise_for_status()
        count_rows = count_response.json().get("results", [])

        location_rows = _read_location_pages(http_client)
        snapshot = _join_live_rows(count_rows, location_rows)

        if not snapshot["sensors"]:
            raise ValueError("The city datasets returned no matching sensors")

        return snapshot
    finally:
        if owns_client:
            http_client.close()


def _read_location_pages(http_client):
    rows = []
    offset = 0

    while offset < 200:
        response = http_client.get(
            LOCATIONS_URL,
            params={"limit": 100, "offset": offset},
        )
        response.raise_for_status()
        data = response.json()
        page = data.get("results", [])
        rows.extend(page)

        if len(rows) >= data.get("total_count", 0) or not page:
            break
        offset += 100

    return rows


def _join_live_rows(count_rows, location_rows):
    locations = {}
    for row in location_rows:
        sensor_id = str(row.get("location_id") or row.get("sensor_id") or "")
        point = _read_point(row)
        if sensor_id and point:
            locations[sensor_id] = {
                "lat": point[0],
                "lon": point[1],
                "name": row.get("sensor_description")
                or row.get("sensor_name")
                or f"Sensor {sensor_id}",
            }

    sensors = []
    timestamps = []
    for row in count_rows:
        sensor_id = str(row.get("location_id") or row.get("sensor_id") or "")
        location = locations.get(sensor_id)
        if not location:
            continue

        timestamp = row.get("sensing_datetime")
        if timestamp:
            timestamps.append(timestamp)

        sensors.append(
            {
                "id": sensor_id,
                "name": location["name"],
                "lat": location["lat"],
                "lon": location["lon"],
                "count": int(row.get("total_count") or 0),
            }
        )

    updated_at = max(timestamps) if timestamps else datetime.now(timezone.utc).isoformat()
    return {
        "source": "live",
        "updated_at": updated_at,
        "sensors": sensors,
        "message": "Live City of Melbourne pedestrian data",
    }


def _read_point(row):
    point = row.get("location") or row.get("geolocation")

    if isinstance(point, dict):
        lat = point.get("lat")
        lon = point.get("lon")
        if lat is not None and lon is not None:
            return float(lat), float(lon)

        coordinates = point.get("coordinates")
        if isinstance(coordinates, list) and len(coordinates) >= 2:
            return float(coordinates[1]), float(coordinates[0])

    lat = row.get("latitude")
    lon = row.get("longitude")
    if lat is not None and lon is not None:
        return float(lat), float(lon)

    return None


def _read_fallback_data():
    data = json.loads(FALLBACK_FILE.read_text(encoding="utf-8"))
    return {
        "source": "fallback",
        "updated_at": None,
        "sensors": data["sensors"],
        "message": "Local sample data (no live timestamp)",
        "cache_status": "fallback",
    }
