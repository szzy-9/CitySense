from datetime import datetime, timezone

import httpx
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from backend.config import Config, ROOT_DIR, read_engine_options
from backend.database import database_health
from backend.models import db
from backend.repositories import (
    data_table_counts,
    database_has_refuges,
)
from backend.services.city_data import (
    get_pedestrian_snapshot,
    get_pedestrian_snapshot_for_departure,
)
from backend.services.geocoding import (
    MAX_AUTOCOMPLETE_RESULTS,
    autocomplete_locations,
)
from backend.services.locations import (
    locations_are_same,
    validate_location,
    validate_route_coordinates,
    validate_search_query,
)
from backend.services.prediction import (
    add_historical_predictions,
    parse_departure_time,
    suggest_calmer_departure,
)
from backend.services.refuges import get_refuges
from backend.services.routing import get_walking_routes
from backend.services.streets import describe_routes_streets
from backend.services.scoring import monitor_route, score_routes


ALLOWED_CROWD_TOLERANCE = {"LOW", "MEDIUM", "HIGH"}
LIVE_DEPARTURE_WINDOW_SECONDS = 5 * 60


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)
        # Pool settings are read from the environment's database at import time.
        # A caller that overrides the URI gets a different backend, and handing
        # SQLite a Postgres pool size fails before a single test runs.
        if "SQLALCHEMY_ENGINE_OPTIONS" not in test_config:
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = read_engine_options(
                app.config["SQLALCHEMY_DATABASE_URI"]
            )

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

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "geolocation=(self), camera=(), microphone=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https://*.tile.openstreetmap.org "
            "https://*.basemaps.cartocdn.com; "
            "font-src 'self'; "
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
        database_status = database_health()
        data_counts = data_table_counts()
        return jsonify(
            {
                "status": "ok" if database_status == "connected" else "degraded",
                "service": "CitySense API",
                "database": {"status": database_status},
                "data": {
                    name: {"loaded": count is not None and count > 0}
                    for name, count in data_counts.items()
                },
            }
        )

    @app.get("/api/data/status")
    def data_status():
        counts = data_table_counts()
        return jsonify(
            {
                name: {
                    "loaded": count is not None and count > 0,
                    "row_count": count,
                }
                for name, count in counts.items()
            }
        )

    @app.get("/api/geocode/autocomplete")
    def geocode_autocomplete():
        try:
            query = validate_search_query(request.args.get("q"))
        except ValueError as error:
            return _error(str(error), 400)

        if not app.config["ORS_API_KEY"]:
            return _error("Address search is unavailable right now.", 503)

        try:
            results = autocomplete_locations(
                query,
                api_key=app.config["ORS_API_KEY"],
                timeout=app.config["REQUEST_TIMEOUT_SECONDS"],
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            app.logger.warning("HeiGIT address autocomplete is unavailable")
            return _error("Address search is temporarily unavailable.", 502)

        return jsonify(
            {
                "results": results[:MAX_AUTOCOMPLETE_RESULTS],
                "data_status": {
                    "source": "heigit_pelias",
                    "result_count": min(
                        len(results),
                        MAX_AUTOCOMPLETE_RESULTS,
                    ),
                },
            }
        )

    @app.get("/api/refuges")
    def refuges():
        origin = None
        origin_values = {
            "lat": request.args.get("lat"),
            "lon": request.args.get("lon"),
            "label": request.args.get("label"),
            "source": request.args.get("source", "current_location"),
        }
        has_origin = any(
            request.args.get(name) is not None
            for name in ("lat", "lon", "label", "source")
        )
        if has_origin:
            try:
                origin = validate_location(origin_values, "Refuge origin")
            except ValueError as error:
                return _error(str(error), 400)

        refuge_list, refuge_source = get_refuges(origin)
        nearest_refuge = refuge_list[0] if origin and refuge_list else None
        calculation_basis = None
        if origin:
            calculation_basis = f"Distance and direction from {origin['label']}."

        return jsonify(
            {
                "refuges": refuge_list,
                "nearest_refuge": nearest_refuge,
                "origin": origin,
                "calculation_basis": calculation_basis,
                "data_status": {
                    "source": refuge_source.lower(),
                    "verified": (
                        all(refuge.get("verified") for refuge in refuge_list)
                        if refuge_source == "NEON" and refuge_list
                        else False
                    ),
                    "message": (
                        "Check the place when you arrive; conditions change."
                        if refuge_source == "NEON"
                        else "We picked these places ourselves. Check them when you arrive."
                    ),
                },
            }
        )

    @app.post("/api/routes")
    def routes():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _error("Send a JSON request body.", 400)

        crowd_tolerance = payload.get("crowd_tolerance", "MEDIUM")
        if (
            not isinstance(crowd_tolerance, str)
            or crowd_tolerance.upper() not in ALLOWED_CROWD_TOLERANCE
        ):
            return _error("Crowd tolerance must be Low, Medium, or High.", 400)

        crowd_tolerance = crowd_tolerance.upper()
        try:
            departure_time, departure_time_defaulted = parse_departure_time(
                payload.get("departure_time")
            )
        except ValueError as error:
            return _error(str(error), 400)
        try:
            start = validate_location(payload.get("start"), "Start")
            end = validate_location(payload.get("end"), "Destination")
        except ValueError as error:
            return _error(str(error), 400)

        if locations_are_same(start, end):
            return _error("Start and destination must be different.", 400)

        pedestrian_snapshot = get_pedestrian_snapshot_for_departure(
            departure_time,
            live_mode=_departure_uses_live_data(
                departure_time,
                departure_time_defaulted,
            ),
            use_live=app.config["USE_LIVE_CITY_DATA"],
            timeout=app.config["REQUEST_TIMEOUT_SECONDS"],
        )
        walking_routes, route_source, route_message = get_walking_routes(
            start,
            end,
            api_key=app.config["ORS_API_KEY"],
            timeout=app.config["REQUEST_TIMEOUT_SECONDS"],
        )
        scored_routes, fastest_id, calmest_id, recommended_id = score_routes(
            walking_routes,
            pedestrian_snapshot,
            route_source=route_source,
            crowd_tolerance=crowd_tolerance,
        )
        add_historical_predictions(
            scored_routes,
            departure_time,
            crowd_tolerance,
            _prediction_thresholds(app.config),
        )
        street_paths = describe_routes_streets(
            [route["geometry"]["coordinates"] for route in scored_routes],
            api_key=app.config["ORS_API_KEY"],
            timeout=app.config["REQUEST_TIMEOUT_SECONDS"],
        )
        for route, street_path in zip(scored_routes, street_paths):
            route["street_path"] = street_path

        selected_route = next(
            route for route in scored_routes if route["id"] == recommended_id
        )
        departure_suggestion = suggest_calmer_departure(
            selected_route,
            departure_time,
            crowd_tolerance,
            _prediction_thresholds(app.config),
        )
        used_fallback = (
            route_source == "fallback"
            or pedestrian_snapshot["source"] == "fallback"
        )
        return jsonify(
            {
                "start": start,
                "end": end,
                "routes": scored_routes,
                "recommended_route_id": recommended_id,
                "departure_suggestion": departure_suggestion,
                "sensors": _unique_route_sensors(scored_routes),
                "request_settings": {
                    "crowd_tolerance": crowd_tolerance,
                    "departure_time": departure_time.isoformat(),
                    "departure_time_defaulted": departure_time_defaulted,
                    "applied_to_routing": True,
                    "message": (
                        "The selected crowd tolerance affects the default recommendation."
                    ),
                },
                "data_status": {
                    "route_source": route_source,
                    "route_message": route_message,
                    "fallback_reason": (
                        scored_routes[0].get("fallback_reason")
                        if route_source == "fallback"
                        else None
                    ),
                    "pedestrian_source": pedestrian_snapshot["source"],
                    "pedestrian_message": pedestrian_snapshot["message"],
                    "updated_at": pedestrian_snapshot["updated_at"],
                    "sensor_count": len(pedestrian_snapshot["sensors"]),
                    "sensor_location_source": pedestrian_snapshot.get(
                        "sensor_location_source", "FALLBACK"
                    ),
                    "historical_profile_source": (
                        "NEON"
                        if any(
                            route["historical_prediction_available"]
                            for route in scored_routes
                        )
                        else "NO_DATA"
                    ),
                    "refuge_source": (
                        "NEON" if database_has_refuges() else "CURATED_PROTOTYPE"
                    ),
                    "cache_status": pedestrian_snapshot.get("cache_status"),
                    "is_fallback": used_fallback,
                },
            }
        )

    @app.post("/api/routes/monitor")
    def monitor_active_route():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _error("Send a JSON request body.", 400)

        crowd_tolerance = payload.get("crowd_tolerance", "MEDIUM")
        if (
            not isinstance(crowd_tolerance, str)
            or crowd_tolerance.upper() not in ALLOWED_CROWD_TOLERANCE
        ):
            return _error("Crowd tolerance must be Low, Medium, or High.", 400)

        try:
            coordinates = validate_route_coordinates(payload.get("coordinates"))
        except ValueError as error:
            return _error(str(error), 400)

        pedestrian_snapshot = get_pedestrian_snapshot(
            use_live=app.config["USE_LIVE_CITY_DATA"],
            timeout=app.config["REQUEST_TIMEOUT_SECONDS"],
        )
        monitoring = monitor_route(
            coordinates,
            pedestrian_snapshot,
            crowd_tolerance.upper(),
        )
        return jsonify(
            {
                **monitoring,
                "data_source": pedestrian_snapshot["source"].upper(),
                "cache_status": pedestrian_snapshot.get("cache_status"),
                "updated_at": pedestrian_snapshot["updated_at"],
            }
        )

    @app.get("/<path:filename>")
    def frontend_fallback(filename):
        if filename.startswith("api/"):
            return _error("API endpoint not found.", 404)

        frontend_dist = ROOT_DIR / "frontend" / "dist"
        requested_file = frontend_dist / filename
        if requested_file.is_file():
            return send_from_directory(frontend_dist, filename)
        if (frontend_dist / "index.html").exists():
            return send_from_directory(frontend_dist, "index.html")
        return _error("Frontend build not found.", 404)

    @app.errorhandler(413)
    def request_too_large(error):
        return _error("Request body is too large.", 413)

    return app


def _error(message, status):
    return jsonify({"error": message}), status


def _unique_route_sensors(routes):
    sensors = {}
    for route in routes:
        for sensor in route.get("matched_sensors", []):
            sensors[sensor["id"]] = sensor
    return list(sensors.values())


def _departure_uses_live_data(departure_time, defaulted, now=None):
    if defaulted:
        return True
    current_time = now or datetime.now(timezone.utc)
    difference = abs(
        (
            departure_time.astimezone(timezone.utc)
            - current_time.astimezone(timezone.utc)
        ).total_seconds()
    )
    return difference <= LIVE_DEPARTURE_WINDOW_SECONDS


def _prediction_thresholds(config):
    return {
        "medium_min_samples": config["PREDICTION_MEDIUM_MIN_SAMPLES"],
        "high_min_samples": config["PREDICTION_HIGH_MIN_SAMPLES"],
        "medium_max_cv": config["PREDICTION_MEDIUM_MAX_CV"],
        "high_max_cv": config["PREDICTION_HIGH_MAX_CV"],
        "minimum_alert_confidence": config["PREDICTION_MIN_ALERT_CONFIDENCE"],
    }


if __name__ == "__main__":
    application = create_app()
    application.run(
        host="127.0.0.1",
        port=application.config["PORT"],
        debug=application.config["DEBUG"],
    )
