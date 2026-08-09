from sqlalchemy.engine import URL

from backend.config import read_database_url, read_engine_options


def test_standard_postgresql_url_uses_installed_psycopg_driver(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://",
    )

    url = read_database_url()

    assert isinstance(url, URL)
    assert url.drivername == "postgresql+psycopg"
    assert url.query["sslmode"] == "require"


def test_postgresql_is_not_built_from_legacy_rds_variables(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("RDS_HOSTNAME", "database.example")
    monkeypatch.setenv("RDS_USERNAME", "citysense")
    monkeypatch.setenv("RDS_PASSWORD", "example")

    url = read_database_url()

    assert isinstance(url, str)
    assert url.startswith("sqlite:///")


def test_neon_url_keeps_ssl_and_uses_small_resilient_pool(monkeypatch):
    example_password = "example-only"
    monkeypatch.setenv(
        "DATABASE_URL",
        (
            "postgresql://citysense:"
            f"{example_password}@host.example/citysense?sslmode=require"
        ),
    )

    url = read_database_url()
    options = read_engine_options(url)

    assert url.drivername == "postgresql+psycopg"
    assert url.query["sslmode"] == "require"
    assert options == {
        "pool_pre_ping": True,
        "pool_size": 3,
        "max_overflow": 2,
        "pool_recycle": 300,
        "connect_args": {"options": "-csearch_path=public"},
    }
