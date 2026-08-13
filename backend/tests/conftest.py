import pytest

from backend.app import create_app
from backend.models import db


@pytest.fixture()
def app():
    test_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "USE_LIVE_CITY_DATA": False,
            "ORS_API_KEY": "",
            "ENABLE_DEMO_AUTH": False,
            "FRONTEND_ORIGIN": (
                "http://127.0.0.1:5173,http://localhost:5173"
            ),
        }
    )

    yield test_app

    with test_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
