from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class RouteSearch(db.Model):
    """Backend-owned operational metadata; no precise locations are stored."""

    __tablename__ = "route_searches"

    id = db.Column(db.Integer, primary_key=True)
    # Legacy database column names are retained so existing local databases work.
    start_source = db.Column("start_id", db.String(80), nullable=False)
    end_source = db.Column("end_id", db.String(80), nullable=False)
    fastest_route_id = db.Column(db.String(40), nullable=False)
    calmest_route_id = db.Column(db.String(40), nullable=False)
    route_source = db.Column(db.String(20), nullable=False)
    pedestrian_source = db.Column(db.String(20), nullable=False)
    selected_route_type = db.Column(db.String(40), nullable=True)
    confidence = db.Column(db.String(10), nullable=True)
    route_count = db.Column(db.Integer, nullable=True)
    used_historical_prediction = db.Column(db.Boolean, nullable=True)
    prediction_confidence = db.Column(db.String(10), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
