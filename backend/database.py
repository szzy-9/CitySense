from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.models import db


def initialize_database():
    """Create missing tables without deleting or replacing existing data."""
    try:
        db.create_all()
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
