import httpx

from backend.services.routing import ORS_URL, get_walking_routes


START = {"label": "Start", "lat": -37.818, "lon": 144.969}
END = {"label": "End", "lat": -37.808, "lon": 144.957}


class FakeResponse:
    def __init__(self, body=None, status_code=200):
        self.body = body if body is not None else success_body()
        request = httpx.Request("POST", ORS_URL)
        self.response = httpx.Response(status_code, request=request)

    @property
    def status_code(self):
        return self.response.status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "Route service rejected the request",
                request=self.response.request,
                response=self.response,
            )

    def json(self):
        return self.body


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response or FakeResponse()
        self.error = error
        self.request = None

    def post(self, url, headers, json):
        self.request = {"url": url, "headers": headers, "json": json}
        if self.error:
            raise self.error
        return self.response


def test_directions_uses_heigit_url_backend_key_and_preserves_steps():
    client = FakeClient()

    routes, source, _ = get_walking_routes(
        START,
        END,
        api_key="test-heigit-key",
        timeout=4,
        client=client,
    )

    assert source == "live"
    assert len(routes) == 2
    assert client.request["url"] == ORS_URL
    assert client.request["headers"] == {"Authorization": "test-heigit-key"}
    assert "test-heigit-key" not in str(client.request["json"])
    assert client.request["json"]["coordinates"][0] == [144.969, -37.818]
    assert client.request["json"]["instructions"] is True
    assert routes[0]["geometry"]["type"] == "LineString"
    assert routes[0]["distance_meters"] == 1000
    assert routes[0]["duration_minutes"] > 0
    assert routes[0]["steps"][0]["instruction"] == "Walk north"
    assert routes[0]["steps"][0]["way_points"] == [0, 1]
    assert routes[0]["source"] == "LIVE"
    assert routes[0]["fallback_reason"] is None


def test_missing_key_returns_explicit_prototype_routes():
    routes, source, message = get_walking_routes(
        START,
        END,
        api_key="",
    )

    assert source == "fallback"
    assert "not configured" in message
    assert all(route["source"] == "PROTOTYPE" for route in routes)
    assert all(route["fallback_reason"] == message for route in routes)
    assert all(route["steps"] == [] for route in routes)


def test_authentication_failure_returns_safe_labelled_fallback():
    client = FakeClient(response=FakeResponse(status_code=401))

    routes, source, message = get_walking_routes(
        START,
        END,
        api_key="invalid-test-key",
        client=client,
    )

    assert source == "fallback"
    assert "authentication failed" in message
    assert "invalid-test-key" not in message
    assert all(route["source"] == "PROTOTYPE" for route in routes)


def test_timeout_returns_safe_labelled_fallback():
    request = httpx.Request("POST", ORS_URL)
    client = FakeClient(error=httpx.ReadTimeout("timed out", request=request))

    routes, source, message = get_walking_routes(
        START,
        END,
        api_key="test-key",
        client=client,
    )

    assert source == "fallback"
    assert "timed out" in message
    assert all(route["fallback_reason"] == message for route in routes)


def test_invalid_external_response_returns_safe_labelled_fallback():
    client = FakeClient(response=FakeResponse(body={"features": "invalid"}))

    routes, source, message = get_walking_routes(
        START,
        END,
        api_key="test-key",
        client=client,
    )

    assert source == "fallback"
    assert "unusable response" in message
    assert len(routes) == 2
    assert all(route["source"] == "PROTOTYPE" for route in routes)


def success_body():
    return {
        "features": [
            route_feature(1000, 700),
            route_feature(1200, 850),
        ]
    }


def route_feature(distance, duration):
    return {
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [144.969, -37.818],
                [144.963, -37.813],
                [144.957, -37.808],
            ],
        },
        "properties": {
            "summary": {"distance": distance, "duration": duration},
            "segments": [
                {
                    "steps": [
                        {
                            "instruction": "Walk north",
                            "distance": distance / 2,
                            "duration": duration / 2,
                            "way_points": [0, 1],
                        },
                        {
                            "instruction": "Continue to the destination",
                            "distance": distance / 2,
                            "duration": duration / 2,
                            "way_points": [1, 2],
                        },
                    ]
                }
            ],
        },
    }
