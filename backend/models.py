from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class RouteSearch(db.Model):
    __tablename__ = "route_searches"

    id = db.Column(db.Integer, primary_key=True)
    start_id = db.Column(db.String(80), nullable=False)
    end_id = db.Column(db.String(80), nullable=False)
    fastest_route_id = db.Column(db.String(40), nullable=False)
    calmest_route_id = db.Column(db.String(40), nullable=False)
    route_source = db.Column(db.String(20), nullable=False)
    pedestrian_source = db.Column(db.String(20), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

