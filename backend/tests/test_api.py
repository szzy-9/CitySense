from sqlalchemy.exc import SQLAlchemyError

from backend.models import db


def test_health_check(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_places_are_available(client):
    response = client.get("/api/places")
    body = response.get_json()

    assert response.status_code == 200
    assert len(body["places"]) >= 6


def test_fallback_returns_two_scored_routes(client):
    response = client.post(
        "/api/routes",
        json={
            "start_id": "federation-square",
            "end_id": "queen-victoria-market",
        },
    )
    body = response.get_json()

    assert response.status_code == 200
    assert len(body["routes"]) == 2
    assert body["data_status"]["route_source"] == "fallback"
    assert body["data_status"]["pedestrian_source"] == "fallback"
    assert body["data_status"]["updated_at"] is None

    roles = []
    for route in body["routes"]:
        roles.extend(route["roles"])

    assert "Fastest" in roles
    assert "Calmest" in roles


def test_same_start_and_end_is_rejected(client):
    response = client.post(
        "/api/routes",
        json={
            "start_id": "federation-square",
            "end_id": "federation-square",
        },
    )

    assert response.status_code == 400
    assert "different" in response.get_json()["error"]


def test_unknown_place_is_rejected(client):
    response = client.post(
        "/api/routes",
        json={"start_id": "not-a-place", "end_id": "carlton-gardens"},
    )

    assert response.status_code == 400


def test_security_headers_are_added(client):
    response = client.get("/api/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]


def test_non_json_route_request_is_rejected(client):
    response = client.post("/api/routes", data="not json")

    assert response.status_code == 400
    assert "JSON" in response.get_json()["error"]


def test_database_error_returns_service_unavailable(client, monkeypatch):
    def fail_to_commit():
        raise SQLAlchemyError("database unavailable")

    monkeypatch.setattr(db.session, "commit", fail_to_commit)
    response = client.post(
        "/api/routes",
        json={
            "start_id": "federation-square",
            "end_id": "queen-victoria-market",
        },
    )

    assert response.status_code == 503
    assert response.get_json()["error"] == "The database is temporarily unavailable."
