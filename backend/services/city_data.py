import json
import logging
import time
from pathlib import Path

import httpx
from flask import has_app_context


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
# Every sensor reports once a minute, so a few hundred of the newest rows cover
# the whole network without pulling the full hour.
COUNT_PAGE_SIZE = 100
COUNT_PAGES = 5
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
        except httpx.ConnectError as error:
            request = getattr(error, "request", None)
            request_url = getattr(request, "url", None)
            cause = getattr(error, "__cause__", None)
            logger.warning(
                "City pedestrian API connection failed: "
                "url=%s error=%s error_repr=%s cause=%s",
                request_url if request_url is not None else "unavailable",
                str(error),
                repr(error),
                repr(cause) if cause is not None else "unavailable",
            )
        except httpx.HTTPStatusError as error:
            logger.warning(
                "City pedestrian API HTTP error: status=%s url=%s response=%s",
                error.response.status_code,
                error.request.url,
                error.response.text[:200],
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
            logger.warning(
                "City pedestrian data is unavailable; using fallback data (%s)",
                type(error).__name__,
            )

    return _read_fallback_data()


def get_pedestrian_snapshot_for_departure(
    departure_time,
    live_mode,
    use_live=True,
    timeout=6,
    client=None,
):
    if live_mode:
        return get_pedestrian_snapshot(
            use_live=use_live,
            timeout=timeout,
            client=client,
        )
    return _read_historical_data(departure_time)


def _cache_is_current():
    return (
        _live_cache["snapshot"] is not None
        and time.monotonic() - _live_cache["stored_at"] <= LIVE_CACHE_SECONDS
    )


def _read_live_data(timeout, client=None):
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout)

    try:
        count_rows = _read_count_pages(http_client)

        location_rows = _read_database_locations()
        location_source = "NEON" if location_rows else "LIVE_API"
        if not location_rows:
            location_rows = _read_location_pages(http_client)
        snapshot = _join_live_rows(count_rows, location_rows)

        # A populated database may be stale or use identifiers that do not match
        # the live count feed. In that case, safely fall back to the live location
        # catalogue instead of treating missing joins as quiet streets.
        if not snapshot["sensors"] and location_source == "NEON":
            location_rows = _read_location_pages(http_client)
            location_source = "LIVE_API"
            snapshot = _join_live_rows(count_rows, location_rows)

        if not snapshot["sensors"]:
            raise ValueError("The city datasets returned no matching sensors")

        snapshot["sensor_location_source"] = location_source
        return snapshot
    finally:
        if owns_client:
            http_client.close()


def _read_count_pages(http_client):
    """The most recent minute each sensor reported.

    The dataset holds one row per sensor per minute for the past hour. Summing
    those rows, as this once did, produces an hour of accumulated footfall -
    twenty thousand people at a busy corner - and comparing that to a
    per-minute threshold classified the entire city as High. Current load is
    the newest row, so the rows are read newest first and the first one seen
    for each sensor wins.
    """
    rows = []
    for page in range(COUNT_PAGES):
        response = http_client.get(
            COUNTS_URL,
            params={
                "order_by": "sensing_datetime desc",
                "limit": COUNT_PAGE_SIZE,
                "offset": page * COUNT_PAGE_SIZE,
            },
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        rows.extend(results)
        if len(results) < COUNT_PAGE_SIZE:
            break

    newest = {}
    for row in rows:
        sensor_id = str(row.get("location_id") or row.get("sensor_id") or "")
        timestamp = row.get("sensing_datetime")
        if not sensor_id or not timestamp:
            continue
        seen = newest.get(sensor_id)
        if seen is None or timestamp > seen["sensing_datetime"]:
            newest[sensor_id] = {
                "location_id": sensor_id,
                "sensing_datetime": timestamp,
                "total_count": _total_of_directions(row),
            }
    return list(newest.values())


def _total_of_directions(row):
    total = row.get("total_of_directions")
    if total is not None:
        return total
    return (row.get("direction_1") or 0) + (row.get("direction_2") or 0)


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


def _read_database_locations():
    if not has_app_context():
        return []
    from backend.repositories import list_active_sensor_locations

    return [
        {
            "location_id": row["location_id"],
            "sensor_description": row["sensor_description"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
        }
        for row in list_active_sensor_locations()
    ]


def _read_historical_data(departure_time):
    if not has_app_context():
        return _empty_historical_snapshot()

    from backend.repositories import (
        get_historical_profiles,
        list_active_sensor_locations,
    )

    locations = list_active_sensor_locations()
    profiles = get_historical_profiles(
        [location["location_id"] for location in locations],
        departure_time,
    )
    sensors = []
    for location in locations:
        profile = profiles.get(location["location_id"])
        if not profile:
            continue
        try:
            count = float(profile["median_per_min"])
        except (KeyError, TypeError, ValueError):
            count = None
        if count is not None and count < 0:
            count = None
        sensors.append(
            {
                "id": location["location_id"],
                "name": location["sensor_description"],
                "lat": location["latitude"],
                "lon": location["longitude"],
                "count": count,
                "sensory_level": (
                    profile["load_band"] if count is not None else "NO_DATA"
                ),
                "confidence": profile["confidence"],
            }
        )

    return {
        "source": "historical",
        "updated_at": None,
        "sensors": sensors,
        "readings": [],
        "message": "Historical crowd profile for the selected departure time",
        "cache_status": None,
        "sensor_location_source": "NEON" if locations else "NO_DATA",
        "count_semantics": (
            "DS median pedestrians per minute for the selected weekday and hour."
        ),
    }


def _empty_historical_snapshot():
    return {
        "source": "historical",
        "updated_at": None,
        "sensors": [],
        "readings": [],
        "message": "Historical crowd profile is unavailable",
        "cache_status": None,
        "sensor_location_source": "NO_DATA",
        "count_semantics": (
            "DS median pedestrians per minute for the selected weekday and hour."
        ),
    }


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
    readings = []
    timestamps = []
    for row in count_rows:
        sensor_id = str(row.get("location_id") or row.get("sensor_id") or "")
        location = locations.get(sensor_id)
        if not location:
            continue

        raw_count = row.get("total_count")
        if raw_count is None:
            continue
        try:
            total_count = int(raw_count)
        except (TypeError, ValueError):
            continue
        if total_count < 0:
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
                "count": total_count,
            }
        )
        readings.append(
            {
                "location_id": sensor_id,
                "sensed_at": timestamp,
                "total_count": total_count,
                "interval_minutes": 1,
                "source": "LIVE",
            }
        )

    updated_at = max(timestamps) if timestamps else None
    return {
        "source": "live",
        "updated_at": updated_at,
        "sensors": sensors,
        "readings": readings,
        "message": "Live City of Melbourne pedestrian data",
        "count_semantics": (
            "People per minute in the most recent minute each sensor reported, "
            "from the City of Melbourne past-hour per-minute dataset; a single "
            "minute is a live reading, not an average."
        ),
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
        "readings": [],
        "message": "Local sample data (no live timestamp)",
        "cache_status": "fallback",
        "sensor_location_source": "FALLBACK",
        "count_semantics": "Local prototype fallback counts.",
    }
