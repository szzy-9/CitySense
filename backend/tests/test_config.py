from sqlalchemy.engine import URL

from backend.config import read_database_url


def test_standard_postgresql_url_uses_installed_psycopg_driver(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://",
    )

    assert read_database_url() == "postgresql+psycopg://"


def test_rds_settings_require_ssl_by_default(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("RDS_HOSTNAME", "database.example")
    monkeypatch.setenv("RDS_USERNAME", "citysense")
    monkeypatch.setenv("RDS_PASSWORD", "example")

    url = read_database_url()

    assert isinstance(url, URL)
    assert url.drivername == "postgresql+psycopg"
    assert url.query["sslmode"] == "require"
