import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL


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
        return url.replace("postgres://", "postgresql+psycopg://", 1)

    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)

    return url


class Config:
    SQLALCHEMY_DATABASE_URI = read_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024

    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    ORS_API_KEY = (
        os.getenv("OPENROUTESERVICE_API_KEY", "").strip()
        or os.getenv("ORS_API_KEY", "").strip()
    )
    USE_LIVE_CITY_DATA = read_boolean("USE_LIVE_CITY_DATA", True)
    REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "6"))
    PORT = int(os.getenv("PORT", "5000"))
    DEBUG = read_boolean("FLASK_DEBUG", False)
