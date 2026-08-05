import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url


ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")


def read_boolean(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def read_database_url():
    default_path = (ROOT_DIR / "citysense.db").as_posix()
    url = os.getenv("DATABASE_URL", "").strip()

    if not url:
        rds_host = os.getenv("RDS_HOSTNAME", "").strip()
        if rds_host:
            ssl_mode = os.getenv("RDS_SSLMODE", "require").strip()
            return URL.create(
                "postgresql+psycopg",
                username=os.getenv("RDS_USERNAME", ""),
                password=os.getenv("RDS_PASSWORD", ""),
                host=rds_host,
                port=int(os.getenv("RDS_PORT", "5432")),
                database=os.getenv("RDS_DB_NAME", "citysense"),
                query={"sslmode": ssl_mode} if ssl_mode else {},
            )
        return f"sqlite:///{default_path}"

    if url == "sqlite:///citysense.db":
        return f"sqlite:///{default_path}"

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    parsed_url = make_url(url)
    if parsed_url.get_backend_name() == "postgresql":
        query = dict(parsed_url.query)
        query.setdefault("sslmode", "require")
        parsed_url = parsed_url.set(query=query)
    return parsed_url


def read_engine_options(database_url):
    parsed_url = make_url(database_url)
    if parsed_url.get_backend_name() == "sqlite":
        return {"pool_pre_ping": True}
    return {
        "pool_pre_ping": True,
        "pool_size": 3,
        "max_overflow": 2,
        "pool_recycle": 300,
    }


class Config:
    SQLALCHEMY_DATABASE_URI = read_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = read_engine_options(SQLALCHEMY_DATABASE_URI)
    MAX_CONTENT_LENGTH = 64 * 1024

    FRONTEND_ORIGIN = os.getenv(
        "ALLOWED_ORIGINS",
        os.getenv(
            "FRONTEND_ORIGIN",
            "http://127.0.0.1:5173,http://localhost:5173",
        ),
    )
    ORS_API_KEY = (
        os.getenv("OPENROUTESERVICE_API_KEY", "").strip()
        or os.getenv("ORS_API_KEY", "").strip()
    )
    USE_LIVE_CITY_DATA = read_boolean("USE_LIVE_CITY_DATA", True)
    REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "6"))
    PORT = int(os.getenv("PORT", "5000"))
    DEBUG = read_boolean("FLASK_DEBUG", False)
    PREDICTION_MEDIUM_MIN_SAMPLES = int(
        os.getenv("PREDICTION_MEDIUM_MIN_SAMPLES", "12")
    )
    PREDICTION_HIGH_MIN_SAMPLES = int(
        os.getenv("PREDICTION_HIGH_MIN_SAMPLES", "30")
    )
    PREDICTION_MEDIUM_MAX_CV = float(
        os.getenv("PREDICTION_MEDIUM_MAX_CV", "1.0")
    )
    PREDICTION_HIGH_MAX_CV = float(
        os.getenv("PREDICTION_HIGH_MAX_CV", "0.5")
    )
    PREDICTION_MIN_ALERT_CONFIDENCE = os.getenv(
        "PREDICTION_MIN_ALERT_CONFIDENCE", "MEDIUM"
    ).upper()
