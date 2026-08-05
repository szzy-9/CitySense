from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from sqlalchemy.exc import SQLAlchemyError

from backend.config import Config, ROOT_DIR
from backend.data.places import PLACES, find_place
from backend.models import RouteSearch, db
from backend.services.city_data import get_pedestrian_snapshot
from backend.services.routing import get_walking_routes
from backend.services.scoring import score_routes


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    allowed_origins = [
        origin.strip()
        for origin in app.config["FRONTEND_ORIGIN"].split(",")
        if origin.strip()
    ]
    CORS(
        app,
        resources={r"/api/*": {"origins": allowed_origins}},
        methods=["GET", "POST", "OPTIONS"],
    )

    with app.app_context():
        db.create_all()

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https://*.tile.openstreetmap.org; "
            "connect-src 'self'"
        )
        if request.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def frontend():
        frontend_dist = ROOT_DIR / "frontend" / "dist"
        index_file = frontend_dist / "index.html"

        if index_file.exists():
            return send_from_directory(frontend_dist, "index.html")

        return jsonify(
            {
                "service": "CitySense API",
                "message": "Build the Vue frontend to serve the full website here.",
            }
        )

    @app.get("/assets/<path:filename>")
    def frontend_asset(filename):
        frontend_dist = ROOT_DIR / "frontend" / "dist" / "assets"
        return send_from_directory(frontend_dist, filename)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "CitySense API"})

    @app.get("/api/places")
    def places():
        return jsonify({"places": PLACES})

    @app.post("/api/routes")
    def routes():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _error("Send a JSON request body.", 400)

        start_id = payload.get("start_id")
        end_id = payload.get("end_id")
        start = find_place(start_id)
        end = find_place(end_id)

        if not start or not end:
            return _error("Choose a valid start and destination.", 400)
        if start_id == end_id:
            return _error("Start and destination must be different.", 400)

        pedestrian_snapshot = get_pedestrian_snapshot(
            use_live=app.config["USE_LIVE_CITY_DATA"],
            timeout=app.config["REQUEST_TIMEOUT_SECONDS"],
        )
        walking_routes, route_source, route_message = get_walking_routes(
            start,
            end,
            api_key=app.config["ORS_API_KEY"],
            timeout=app.config["REQUEST_TIMEOUT_SECONDS"],
        )
        scored_routes, fastest_id, calmest_id = score_routes(
            walking_routes,
            pedestrian_snapshot,
        )

        search = RouteSearch(
            start_id=start_id,
            end_id=end_id,
            fastest_route_id=fastest_id,
            calmest_route_id=calmest_id,
            route_source=route_source,
            pedestrian_source=pedestrian_snapshot["source"],
        )
        db.session.add(search)
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Could not save the route search")
            return _error("The database is temporarily unavailable.", 503)

        used_fallback = (
            route_source == "fallback"
            or pedestrian_snapshot["source"] == "fallback"
        )
        return jsonify(
            {
                "start": start,
                "end": end,
                "routes": scored_routes,
                "data_status": {
                    "route_source": route_source,
                    "route_message": route_message,
                    "pedestrian_source": pedestrian_snapshot["source"],
                    "pedestrian_message": pedestrian_snapshot["message"],
                    "updated_at": pedestrian_snapshot["updated_at"],
                    "sensor_count": len(pedestrian_snapshot["sensors"]),
                    "is_fallback": used_fallback,
                },
            }
        )

    @app.errorhandler(413)
    def request_too_large(error):
        return _error("Request body is too large.", 413)

    return app


def _error(message, status):
    return jsonify({"error": message}), status


if __name__ == "__main__":
    application = create_app()
    application.run(
        host="127.0.0.1",
        port=application.config["PORT"],
        debug=application.config["DEBUG"],
    )
