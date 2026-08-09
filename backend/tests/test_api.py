from datetime import datetime, timezone

from backend.models import db


START = {
    "label": "Federation Square, Melbourne VIC",
    "lat": -37.81798,
    "lon": 144.96913,
    "source": "autocomplete",
}
END = {
    "label": "Queen Victoria Market, Melbourne VIC",
    "lat": -37.80758,
    "lon": 144.95678,
    "source": "autocomplete",
}


def route_payload(**changes):
    payload = {
        "start": dict(START),
        "end": dict(END),
        "crowd_tolerance": "MEDIUM",
    }
    payload.update(changes)
    return payload


def test_health_check(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
    assert response.get_json()["database"]["status"] == "connected"


def test_health_check_reports_database_degraded_without_details(
    client,
    monkeypatch,
):
    monkeypatch.setattr("backend.app.database_health", lambda: "degraded")

    response = client.get("/api/health")
    body = response.get_json()

    assert response.status_code == 200
    assert body["status"] == "degraded"
    assert body["service"] == "CitySense API"
    assert body["database"] == {"status": "degraded"}
    assert body["data"]["sensor_locations"]["loaded"] is False
    assert "url" not in str(body).lower()
    assert "password" not in str(body).lower()


def test_fixed_places_endpoint_is_removed(client):
    response = client.get("/api/places")

    assert response.status_code == 404


def test_autocomplete_returns_limited_confirmable_results(
    app,
    client,
    monkeypatch,
):
    def fake_autocomplete(query, api_key, timeout):
        assert query == "Flinders Street"
        assert api_key == "test-heigit-key"
        assert timeout > 0
        return [
            {
                "id": f"result-{index}",
                "label": f"Flinders Street result {index}",
                "lat": -37.818 + index * 0.0001,
                "lon": 144.967 + index * 0.0001,
                "source": "heigit_pelias",
            }
            for index in range(8)
        ]

    app.config["ORS_API_KEY"] = "test-heigit-key"
    monkeypatch.setattr(
        "backend.app.autocomplete_locations",
        fake_autocomplete,
        raising=False,
    )

    response = client.get(
        "/api/geocode/autocomplete",
        query_string={"q": "Flinders Street"},
    )
    body = response.get_json()

    assert response.status_code == 200
    assert len(body["results"]) == 5
    assert body["data_status"]["source"] == "heigit_pelias"
    assert "api_key" not in str(body).lower()


def test_autocomplete_rejects_short_or_oversized_queries(client):
    short = client.get(
        "/api/geocode/autocomplete",
        query_string={"q": "a"},
    )
    oversized = client.get(
        "/api/geocode/autocomplete",
        query_string={"q": "x" * 121},
    )

    assert short.status_code == 400
    assert oversized.status_code == 400


def test_autocomplete_requires_a_backend_api_key(client):
    response = client.get(
        "/api/geocode/autocomplete",
        query_string={"q": "Flinders Street"},
    )

    assert response.status_code == 503
    # Say the feature is unavailable without naming our provider or its keys.
    error = response.get_json()["error"]
    assert "unavailable" in error
    assert "key" not in error.lower()


def test_refuges_accept_a_validated_coordinate_origin(client):
    response = client.get(
        "/api/refuges",
        query_string={
            "lat": START["lat"],
            "lon": START["lon"],
            "label": START["label"],
        },
    )
    body = response.get_json()

    assert response.status_code == 200
    assert len(body["refuges"]) >= 3
    assert body["nearest_refuge"]["distance_meters"] > 0
    assert body["nearest_refuge"]["verified"] is False
    assert body["refuges"][0]["id"] == body["nearest_refuge"]["id"]
    assert body["refuges"][0]["distance_meters"] <= body["refuges"][1][
        "distance_meters"
    ]
    assert body["origin"]["label"] == START["label"]
    assert body["data_status"]["source"] == "curated_prototype"


def test_refuges_reject_invalid_coordinates(client):
    response = client.get(
        "/api/refuges",
        query_string={"lat": -20, "lon": 150, "label": "Outside area"},
    )

    assert response.status_code == 400


def test_fallback_returns_two_scored_routes_for_coordinates(client):
    response = client.post("/api/routes", json=route_payload())
    body = response.get_json()

    assert response.status_code == 200
    assert body["start"]["label"] == START["label"]
    assert body["end"]["label"] == END["label"]
    assert len(body["routes"]) == 2
    assert body["data_status"]["route_source"] == "fallback"
    assert body["data_status"]["pedestrian_source"] == "fallback"
    assert body["data_status"]["updated_at"] is None
    assert body["request_settings"]["applied_to_routing"] is True
    assert body["recommended_route_id"]

    roles = []
    for route in body["routes"]:
        roles.extend(route["roles"])
        assert route["segments"]
        assert route["data_status"] == "PROTOTYPE"
        assert route["confidence"] == "LOW"
        assert route["confidence_reasons"]
        assert route["source"] == "PROTOTYPE"
        assert route["fallback_reason"]
        assert route["sensory_indicator"] == "NO_DATA"
        assert route["peak_load"] in {"LOW", "MODERATE", "HIGH", "NO_DATA"}
        assert isinstance(route["recommended"], bool)
        assert route["congestion_avoidable"] is False
        assert route["recommendation_reason"]
        assert route["sensor_count"] == route["matched_sensor_count"]
        assert route["sensory_level"] in {"LOW", "MODERATE", "HIGH", "NO_DATA"}
        assert route["historical_prediction_available"] is False
        assert route["predicted_peak"] == "NO_DATA"
        assert route["predicted_count"] is None
        assert route["prediction_confidence"] == "LOW"
        assert route["prediction_alert"] is None
        assert route["prediction_unavailable_reason"] == (
            "We have no past pattern for this route at this time of day."
        )

    assert "Fastest" in roles
    assert "Calmest" in roles


def test_same_coordinates_are_rejected(client):
    response = client.post(
        "/api/routes",
        json=route_payload(end=dict(START)),
    )

    assert response.status_code == 400
    assert "different" in response.get_json()["error"]


def test_route_rejects_unconfirmed_or_invalid_location_data(client):
    missing_confirmation = client.post(
        "/api/routes",
        json=route_payload(start={"label": "Typed but not selected"}),
    )
    outside_bounds = client.post(
        "/api/routes",
        json=route_payload(
            start={
                "label": "Outside supported area",
                "lat": -20,
                "lon": 150,
                "source": "autocomplete",
            }
        ),
    )

    assert missing_confirmation.status_code == 400
    assert outside_bounds.status_code == 400


def test_invalid_crowd_tolerance_is_rejected(client):
    response = client.post(
        "/api/routes",
        json=route_payload(crowd_tolerance="EXTREME"),
    )

    assert response.status_code == 400
    assert "Low, Medium, or High" in response.get_json()["error"]


def test_departure_time_must_include_a_timezone(client):
    response = client.post(
        "/api/routes",
        json=route_payload(departure_time="2026-08-06T09:30:00"),
    )

    assert response.status_code == 400
    assert "timezone" in response.get_json()["error"]


def test_missing_departure_time_uses_a_documented_default(client):
    response = client.post("/api/routes", json=route_payload())
    settings = response.get_json()["request_settings"]

    assert response.status_code == 200
    assert settings["departure_time_defaulted"] is True
    assert "+" in settings["departure_time"]


def test_data_status_reports_safe_counts(client):
    response = client.get("/api/data/status")
    body = response.get_json()

    assert response.status_code == 200
    assert body["sensor_locations"] == {"loaded": False, "row_count": None}
    assert body["pedestrian_readings"] == {
        "loaded": False,
        "row_count": None,
    }
    assert "url" not in str(body).lower()
    assert "password" not in str(body).lower()


def test_reroute_source_uses_current_position_and_preserves_destination(client):
    current = {
        "label": "Current Location",
        "lat": -37.816,
        "lon": 144.968,
        "source": "reroute",
    }

    response = client.post(
        "/api/routes",
        json=route_payload(start=current, crowd_tolerance="LOW"),
    )
    body = response.get_json()

    assert response.status_code == 200
    assert body["start"] == current
    assert body["end"] == END
    assert body["request_settings"]["crowd_tolerance"] == "LOW"


def test_route_monitor_validates_geometry_and_threshold(client):
    invalid_geometry = client.post(
        "/api/routes/monitor",
        json={"coordinates": [[144.96, -37.81]], "crowd_tolerance": "MEDIUM"},
    )
    invalid_threshold = client.post(
        "/api/routes/monitor",
        json={
            "coordinates": [[144.96, -37.81], [144.97, -37.82]],
            "crowd_tolerance": "EXTREME",
        },
    )
    too_many_points = client.post(
        "/api/routes/monitor",
        json={
            "coordinates": [[144.96, -37.81] for _ in range(501)],
            "crowd_tolerance": "MEDIUM",
        },
    )

    assert invalid_geometry.status_code == 400
    assert invalid_threshold.status_code == 400
    assert too_many_points.status_code == 400


def test_route_monitor_uses_pedestrian_data_without_requesting_new_route(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        "backend.app.get_pedestrian_snapshot",
        lambda **kwargs: {
            "source": "live",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "cache_status": "cached",
            "sensors": [
                {
                    "id": "sensor-1",
                    "name": "Test sensor",
                    "lat": -37.81,
                    "lon": 144.965,
                    "count": 700,
                    "sensory_level": "HIGH",
                }
            ],
        },
    )

    response = client.post(
        "/api/routes/monitor",
        json={
            "coordinates": [[144.96, -37.81], [144.97, -37.81]],
            "crowd_tolerance": "MEDIUM",
        },
    )
    body = response.get_json()

    assert response.status_code == 200
    assert body["breached"] is True
    assert body["upcoming_peak"] == "HIGH"
    assert body["data_source"] == "LIVE"
    assert body["cache_status"] == "cached"


def test_security_headers_allow_same_origin_geolocation(client):
    response = client.get("/api/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Permissions-Policy"] == (
        "geolocation=(self), camera=(), microphone=()"
    )
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]


def test_cors_allows_only_a_configured_frontend_origin(client):
    allowed = client.get(
        "/api/health",
        headers={"Origin": "http://127.0.0.1:5173"},
    )
    untrusted = client.get(
        "/api/health",
        headers={"Origin": "https://untrusted.example"},
    )

    assert allowed.headers["Access-Control-Allow-Origin"] == (
        "http://127.0.0.1:5173"
    )
    assert "Access-Control-Allow-Origin" not in untrusted.headers


def test_non_json_route_request_is_rejected(client):
    response = client.post("/api/routes", data="not json")

    assert response.status_code == 400
    assert "JSON" in response.get_json()["error"]


def test_route_generation_does_not_write_search_metadata(client, monkeypatch):
    def unexpected_write(*args, **kwargs):
        raise AssertionError("/api/routes must not write route-search metadata")

    monkeypatch.setattr(db.session, "add", unexpected_write)
    monkeypatch.setattr(db.session, "commit", unexpected_write)
    response = client.post("/api/routes", json=route_payload())

    assert response.status_code == 200
