"""The streets a walking route actually follows.

A sensory score tells someone how a trip will feel. It does not tell them which
way they are going, and a route they cannot picture is a route they cannot
sanity-check against what they already know about the city.

OpenRouteService cannot answer this on its own. Melbourne's footpaths are
mapped as unnamed ways alongside the road they run beside, so most walking
steps come back named "-" and the longest leg of a CBD trip is usually one of
them. The names have to be looked up from the coordinates instead.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

import httpx

from backend.services.locations import haversine_distance


REVERSE_URL = "https://api.heigit.org/pelias/v1/reverse"

# Enough points to catch every street worth naming on a CBD walk, few enough
# that a lookup stays one round trip wide.
MAX_SAMPLES = 6
MAX_NAMES = 5
CACHE_LIMIT = 4000

# The grid is small and its street names do not move, so a coarse cache spares
# almost every repeat lookup. Four decimal places is roughly eleven metres.
_cache = {}
logger = logging.getLogger(__name__)

# A reverse lookup will happily return a loading dock or a building name. Only
# something that reads as a thoroughfare belongs in "which way am I going".
STREET_SUFFIXES = {
    "street": "St",
    "road": "Rd",
    "lane": "Ln",
    "avenue": "Ave",
    "place": "Pl",
    "parade": "Pde",
    "boulevard": "Bvd",
    "highway": "Hwy",
    "terrace": "Tce",
    "drive": "Dr",
    "crescent": "Cres",
    "esplanade": "Esp",
    "square": "Sq",
    "walk": "Walk",
    "way": "Way",
    "bridge": "Bridge",
    "alley": "Alley",
    "arcade": "Arcade",
    "promenade": "Promenade",
}


def describe_routes_streets(routes_coordinates, api_key, timeout=6, client=None):
    """Ordered street names for several routes at once.

    Every route is looked up in the same batch. Doing them one after another
    added a round trip per route to a request the user is already waiting on,
    and the alternatives being compared overlap heavily anyway.
    """
    if not api_key:
        return [[] for _ in routes_coordinates]

    samples = [
        _sample_coordinates(coordinates, MAX_SAMPLES)
        if coordinates and len(coordinates) >= 2
        else []
        for coordinates in routes_coordinates
    ]
    pending = {
        _cache_key(point)
        for route_samples in samples
        for point in route_samples
        if _cache_key(point) not in _cache
    }

    if pending:
        owns_client = client is None
        http_client = client or httpx.Client(timeout=timeout)
        points = [point for point in _unique_points(samples) if _cache_key(point) in pending]
        try:
            with ThreadPoolExecutor(max_workers=min(len(points), 12)) as pool:
                pool.map(lambda point: _street_at(point, api_key, http_client), points)
        except (httpx.HTTPError, RuntimeError, ValueError):
            logger.warning("Street naming is unavailable for these routes")
            return [[] for _ in routes_coordinates]
        finally:
            if owns_client:
                http_client.close()

    return [
        _condense([_cache.get(_cache_key(point)) for point in route_samples])
        for route_samples in samples
    ]


def _cache_key(point):
    return (round(point[1], 4), round(point[0], 4))


def _unique_points(samples):
    seen = set()
    points = []
    for route_samples in samples:
        for point in route_samples:
            key = _cache_key(point)
            if key not in seen:
                seen.add(key)
                points.append(point)
    return points


def _sample_coordinates(coordinates, count):
    """Evenly spaced points by distance walked, not by vertex index.

    Route geometry bunches vertices around corners, so sampling the list
    directly would name the same intersection several times over and miss the
    long straight stretch between them.
    """
    lengths = [0.0]
    for index in range(len(coordinates) - 1):
        lengths.append(
            lengths[-1]
            + haversine_distance(coordinates[index], coordinates[index + 1])
        )
    total = lengths[-1]
    if total <= 0:
        return [coordinates[0]]

    samples = []
    vertex = 0
    for step in range(count):
        target = total * (step + 0.5) / count
        while vertex < len(lengths) - 1 and lengths[vertex + 1] < target:
            vertex += 1
        samples.append(coordinates[min(vertex, len(coordinates) - 1)])
    return samples


def _street_at(point, api_key, http_client):
    key = _cache_key(point)
    if key in _cache:
        return _cache[key]

    try:
        response = http_client.get(
            REVERSE_URL,
            headers={"Authorization": api_key},
            params={
                "point.lat": point[1],
                "point.lon": point[0],
                "size": 1,
                "layers": "street,address",
            },
        )
        response.raise_for_status()
        features = response.json().get("features", [])
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        return None

    properties = features[0].get("properties", {}) if features else {}
    name = _shorten(properties.get("street") or properties.get("name"))

    if len(_cache) >= CACHE_LIMIT:
        _cache.clear()
    _cache[key] = name
    return name


def _shorten(name):
    if not isinstance(name, str) or not name.strip():
        return None

    words = name.strip().split()
    suffix = STREET_SUFFIXES.get(words[-1].lower())
    if not suffix:
        return None
    return " ".join(words[:-1] + [suffix])


def _condense(names):
    """Each street once, in the order it is first reached.

    Clipping a corner puts a cross street between two samples of the same road,
    which came out as "Elizabeth St, Bourke St, Elizabeth St" and read as a
    fault rather than as a route. This is a summary of the streets a walk uses,
    not turn-by-turn directions, so naming each one once is both tidier and
    closer to what it honestly claims to be.
    """
    ordered = []
    for name in names:
        if name and name not in ordered:
            ordered.append(name)
    return ordered[:MAX_NAMES]
