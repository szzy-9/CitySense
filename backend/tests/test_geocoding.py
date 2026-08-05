import pytest

from backend.services.geocoding import (
    AUTOCOMPLETE_URL,
    autocomplete_locations,
)
from backend.services.locations import validate_location, validate_search_query


class FakeResponse:
    def __init__(self, features):
        self.features = features

    def raise_for_status(self):
        return None

    def json(self):
        return {"features": self.features}


class FakeClient:
    def __init__(self, features):
        self.features = features
        self.request = None

    def get(self, url, params, headers):
        self.request = {"url": url, "params": params, "headers": headers}
        return FakeResponse(self.features)


def test_autocomplete_uses_heigit_url_key_header_limit_and_melbourne_bounds():
    features = [
        feature(
            f"place-{index}",
            f"Address {index}",
            144.96 + index * 0.001,
            -37.82 + index * 0.001,
        )
        for index in range(7)
    ]
    features.append(feature("outside", "Outside", 150, -20))
    client = FakeClient(features)

    results = autocomplete_locations(
        "Flinders Street",
        api_key="test-heigit-key",
        timeout=4,
        client=client,
    )

    assert client.request["url"] == AUTOCOMPLETE_URL
    assert client.request["headers"] == {"Authorization": "test-heigit-key"}
    assert "api_key" not in client.request["params"]
    assert client.request["params"]["size"] == 5
    assert client.request["params"]["boundary.country"] == "AU"
    assert client.request["params"]["boundary.rect.min_lon"] == 144.92
    assert client.request["params"]["boundary.rect.max_lon"] == 145.02
    assert len(results) == 5
    assert all(result["source"] == "heigit_pelias" for result in results)


def test_location_validation_requires_confirmation_and_supported_coordinates():
    with pytest.raises(ValueError, match="confirmed"):
        validate_location(None, "Start")
    with pytest.raises(ValueError, match="selected or confirmed"):
        validate_location(
            {"label": "Typed only", "lat": -37.81, "lon": 144.96},
            "Start",
        )
    with pytest.raises(ValueError, match="outside"):
        validate_location(
            {
                "label": "Sydney",
                "lat": -33.86,
                "lon": 151.2,
                "source": "autocomplete",
            },
            "Start",
        )


def test_search_query_is_trimmed_and_length_limited():
    assert validate_search_query("  Flinders   Street  ") == "Flinders Street"
    with pytest.raises(ValueError):
        validate_search_query("x")
    with pytest.raises(ValueError):
        validate_search_query("x" * 121)


def feature(feature_id, label, lon, lat):
    return {
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"gid": feature_id, "label": label},
    }
