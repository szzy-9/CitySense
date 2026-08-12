import pytest
from werkzeug.security import generate_password_hash

from backend.app import create_app
from backend.models import db


TEST_PASSWORD = "test-only-demo-password"
TEST_PASSWORD_HASH = generate_password_hash(TEST_PASSWORD)
TEST_SESSION_SECRET = "test-only-session-secret"
TEST_API_KEY = "test-only-api-key"
TEST_DATABASE_URL = "postgresql://test-user:test-password@db.invalid/test-db"


@pytest.fixture()
def secured_app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "USE_LIVE_CITY_DATA": False,
            "ORS_API_KEY": TEST_API_KEY,
            "FRONTEND_ORIGIN": "https://citysense.example",
            "ENABLE_DEMO_AUTH": True,
            "DEMO_ACCESS_PASSWORD_HASH": TEST_PASSWORD_HASH,
            "SECRET_KEY": TEST_SESSION_SECRET,
            "SESSION_COOKIE_SECURE": True,
            "SESSION_COOKIE_HTTPONLY": True,
            "SESSION_COOKIE_SAMESITE": "Lax",
            "IS_PRODUCTION": True,
        }
    )
    # A marker lets the response tests detect accidental configuration dumps
    # without asking SQLAlchemy to connect to a fake PostgreSQL server.
    app.config["DATABASE_URL"] = TEST_DATABASE_URL

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def secured_client(secured_app):
    return secured_app.test_client()


def test_demo_auth_disabled_preserves_normal_local_access(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers.get("Location") is None
    assert "Strict-Transport-Security" not in response.headers


def test_request_size_limit_remains_enabled(client):
    response = client.post(
        "/api/routes",
        data=b"x" * (64 * 1024 + 1),
        content_type="application/json",
    )

    assert response.status_code == 413
    assert response.get_json() == {"error": "Request body is too large."}


def test_unauthenticated_application_redirects_to_login(secured_client):
    response = secured_client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_unauthenticated_api_is_rejected_but_health_remains_public(
    secured_client,
):
    protected = secured_client.get("/api/data/status")
    health = secured_client.get("/api/health")

    assert protected.status_code == 401
    assert protected.get_json() == {"error": "Authentication required."}
    assert health.status_code == 200
    assert health.get_json()["service"] == "CitySense API"


def test_static_assets_are_not_redirected_to_login(secured_client):
    response = secured_client.get("/assets/not-present.js")

    assert response.status_code == 404
    assert response.headers.get("Location") is None


def test_correct_password_creates_only_authenticated_session(secured_client):
    response = secured_client.post(
        "/login",
        data={"password": TEST_PASSWORD},
        base_url="https://localhost",
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    with secured_client.session_transaction() as authenticated_session:
        assert dict(authenticated_session) == {"demo_authenticated": True}
    protected = secured_client.get(
        "/api/data/status",
        base_url="https://localhost",
    )
    assert protected.status_code == 200


def test_incorrect_password_does_not_authenticate_or_expose_secrets(
    secured_client,
):
    response = secured_client.post(
        "/login",
        data={"password": "wrong-test-password"},
        base_url="https://localhost",
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Incorrect password." in body
    with secured_client.session_transaction() as anonymous_session:
        assert "demo_authenticated" not in anonymous_session
    for secret in (
        TEST_PASSWORD,
        TEST_PASSWORD_HASH,
        TEST_SESSION_SECRET,
        TEST_API_KEY,
        TEST_DATABASE_URL,
    ):
        assert secret not in body


def test_production_session_cookie_has_required_security_flags(secured_client):
    response = secured_client.post(
        "/login",
        data={"password": TEST_PASSWORD},
        base_url="https://localhost",
    )
    cookie = response.headers["Set-Cookie"]

    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_production_security_headers_and_strict_cors_remain_enabled(
    secured_client,
):
    allowed = secured_client.get(
        "/api/health",
        headers={"Origin": "https://citysense.example"},
    )
    untrusted = secured_client.get(
        "/api/health",
        headers={"Origin": "https://untrusted.example"},
    )

    assert allowed.headers["Strict-Transport-Security"] == "max-age=31536000"
    assert allowed.headers["Content-Security-Policy"].startswith(
        "default-src 'self'"
    )
    assert allowed.headers["X-Frame-Options"] == "DENY"
    assert allowed.headers["X-Content-Type-Options"] == "nosniff"
    assert allowed.headers["Referrer-Policy"] == "no-referrer"
    assert allowed.headers["Permissions-Policy"] == (
        "geolocation=(self), camera=(), microphone=()"
    )
    assert allowed.headers["Access-Control-Allow-Origin"] == (
        "https://citysense.example"
    )
    assert "Access-Control-Allow-Origin" not in untrusted.headers


def test_public_and_rejected_api_responses_do_not_expose_configuration(
    secured_client,
):
    responses = [
        secured_client.get("/api/health"),
        secured_client.get("/api/data/status"),
    ]
    combined_body = " ".join(
        response.get_data(as_text=True) for response in responses
    )

    for secret in (
        TEST_PASSWORD,
        TEST_PASSWORD_HASH,
        TEST_SESSION_SECRET,
        TEST_API_KEY,
        TEST_DATABASE_URL,
    ):
        assert secret not in combined_body


def test_logout_clears_authenticated_session(secured_client):
    secured_client.post(
        "/login",
        data={"password": TEST_PASSWORD},
        base_url="https://localhost",
    )

    response = secured_client.post("/logout", base_url="https://localhost")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with secured_client.session_transaction() as anonymous_session:
        assert "demo_authenticated" not in anonymous_session
