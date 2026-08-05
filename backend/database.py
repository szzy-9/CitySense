from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from backend.models import db


def initialize_database():
    """Create missing tables without deleting or replacing existing data."""
    try:
        db.create_all()
        _add_route_search_metadata_columns()
        return True
    except SQLAlchemyError:
        safe_rollback()
        return False


def database_health():
    try:
        db.session.execute(text("SELECT 1"))
        return "connected"
    except SQLAlchemyError:
        safe_rollback()
        return "degraded"


def safe_rollback():
    try:
        db.session.rollback()
        return True
    except SQLAlchemyError:
        return False


def _add_route_search_metadata_columns():
    """Add nullable metadata columns to older databases without replacing data."""
    inspector = inspect(db.engine)
    if "route_searches" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("route_searches")}
    additions = {
        "selected_route_type": "VARCHAR(40)",
        "confidence": "VARCHAR(10)",
        "route_count": "INTEGER",
        "used_historical_prediction": "BOOLEAN",
        "prediction_confidence": "VARCHAR(10)",
    }
    for name, sql_type in additions.items():
        if name not in existing:
            db.session.execute(
                text(f"ALTER TABLE route_searches ADD COLUMN {name} {sql_type}")
            )
    db.session.commit()
