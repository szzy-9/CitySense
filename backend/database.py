from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.models import db


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
