from datetime import datetime, timezone

from backend.services.scoring import (
    HIGH,
    LOW,
    MODERATE,
    NO_DATA,
    calculate_confidence,
    load_level_for_count,
    monitor_route,
    route_sensory_indicator,
    score_routes,
    select_calmest_route,
    select_recommended_route,
    worst_load_level,
)


def test_worst_load_returns_high_for_mixed_levels():
    assert worst_load_level([LOW, MODERATE, HIGH]) == HIGH


def test_worst_load_returns_moderate_when_it_is_the_peak():
    assert worst_load_level([LOW, MODERATE]) == MODERATE


def test_worst_load_returns_low_when_every_segment_is_low():
    assert worst_load_level([LOW, LOW]) == LOW


def test_no_data_is_not_treated_as_low():
    assert worst_load_level([NO_DATA]) == NO_DATA
    assert worst_load_level([NO_DATA, MODERATE]) == MODERATE


def test_load_band_boundaries_are_explicit():
    # People per minute, the unit the live feed reports.
    assert load_level_for_count(None) == NO_DATA
    assert load_level_for_count(50) == LOW
    assert load_level_for_count(51) == MODERATE
    assert load_level_for_count(150) == MODERATE
    assert load_level_for_count(151) == HIGH


def test_route_without_reliable_segments_returns_no_data():
    scored, _, _, recommended_id = score_routes(
        [_route("route-1", -37.81, 15)],
        _snapshot([]),
        route_source="live",
    )

    assert scored[0]["sensory_level"] == NO_DATA
    assert scored[0]["peak_load"] == NO_DATA
    assert scored[0]["sensory_indicator"] == NO_DATA
    assert scored[0]["coverage"] == 0
    assert scored[0]["confidence"] == "LOW"
    assert scored[0]["confidence_reasons"]
    assert recommended_id == "route-1"
    assert scored[0]["congestion_avoidable"] is False


def test_calmest_tie_break_prefers_coverage_then_average_then_duration():
    routes = [
        _scored_route("short-low-coverage", MODERATE, 0.4, 150, 10),
        _scored_route("covered", MODERATE, 0.8, 250, 14),
        _scored_route("covered-lower-average", MODERATE, 0.8, 180, 16),
        _scored_route("winner", MODERATE, 0.8, 180, 12),
    ]

    assert select_calmest_route(routes)["id"] == "winner"


def test_high_confidence_requires_live_fresh_well_covered_data():
    confidence, explanation = calculate_confidence(
        route_source="live",
        pedestrian_source="live",
        updated_at=datetime.now(timezone.utc).isoformat(),
        sensor_count=4,
        coverage=0.75,
        sensory_level=MODERATE,
    )

    assert confidence == "HIGH"
    assert "4 sensors" in explanation


def test_prototype_route_always_has_low_confidence_and_no_data_indicator():
    confidence, explanation = calculate_confidence(
        route_source="fallback",
        pedestrian_source="live",
        updated_at=datetime.now(timezone.utc).isoformat(),
        sensor_count=5,
        coverage=1,
        sensory_level=LOW,
    )

    indicator = route_sensory_indicator(
        LOW,
        1,
        "fallback",
        "live",
        "MEDIUM",
        updated_at=datetime.now(timezone.utc).isoformat(),
    )

    assert confidence == "LOW"
    # An example route must say so rather than implying it is live.
    assert "example route" in explanation
    assert indicator == NO_DATA


def test_threshold_boundaries_map_peak_to_binary_indicator():
    assert _indicator(LOW, "LOW") == LOW
    assert _indicator(MODERATE, "LOW") == HIGH
    assert _indicator(MODERATE, "MEDIUM") == LOW
    assert _indicator(HIGH, "MEDIUM") == HIGH
    assert _indicator(HIGH, "HIGH") == LOW
    assert _indicator(NO_DATA, "HIGH") == NO_DATA


def test_stale_observations_do_not_receive_a_low_indicator():
    indicator = route_sensory_indicator(
        LOW,
        coverage=1,
        route_source="live",
        pedestrian_source="live",
        crowd_tolerance="LOW",
        updated_at="2020-01-01T00:00:00+00:00",
    )

    assert indicator == NO_DATA


def test_above_threshold_route_is_not_default_when_lower_route_exists():
    high = _recommendation_route("fast-high", HIGH, HIGH, 1, 600, 10)
    low = _recommendation_route("calm-low", LOW, LOW, 0.8, 100, 14)

    recommended, avoidable, _ = select_recommended_route([high, low])

    assert recommended["id"] == "calm-low"
    assert avoidable is True


def test_all_candidates_above_threshold_returns_unavoidable_explanation():
    routes = [
        _recommendation_route("high-a", HIGH, HIGH, 0.8, 650, 10),
        _recommendation_route("high-b", HIGH, HIGH, 1, 550, 12),
    ]

    recommended, avoidable, reason = select_recommended_route(routes)

    assert recommended["id"] == "high-b"
    assert avoidable is False
    # When every option breaches the limit, say so instead of implying a safe pick,
    # while still explaining why this one was chosen.
    assert "Every route" in reason
    assert "calmest at its busiest point" in reason


def test_all_candidates_no_data_never_claims_congestion_was_avoided():
    routes = [
        _recommendation_route("unknown-a", NO_DATA, NO_DATA, 0, None, 10),
        _recommendation_route("unknown-b", NO_DATA, NO_DATA, 0, None, 12),
    ]

    _, avoidable, reason = select_recommended_route(routes)

    assert avoidable is False
    # The reason must not promise a calmer route when nothing was observed.
    assert "not enough crowd data" in reason


def test_observed_high_is_preferred_to_unknown_route_without_false_claim():
    routes = [
        _recommendation_route("unknown", NO_DATA, NO_DATA, 0, None, 9),
        _recommendation_route("observed", HIGH, HIGH, 0.8, 700, 12),
    ]

    recommended, avoidable, reason = select_recommended_route(routes)

    assert recommended["id"] == "observed"
    assert avoidable is False
    # Missing data must be named, not silently presented as a calm result.
    assert "missing crowd data" in reason


def test_fastest_high_and_calmest_low_recommends_calmest_for_low_tolerance():
    routes = [
        _route("fast", -37.8100, 10),
        _route("calm", -37.8140, 14),
    ]
    sensors = [
        _sensor("high", -37.8100, 700),
        _sensor("low", -37.8140, 30),
    ]

    scored, fastest_id, calmest_id, recommended_id = score_routes(
        routes,
        _snapshot(sensors),
        route_source="live",
        crowd_tolerance="LOW",
    )

    assert fastest_id == "fast"
    assert calmest_id == "calm"
    assert recommended_id == "calm"
    assert next(route for route in scored if route["id"] == "fast")[
        "sensory_indicator"
    ] == HIGH
    assert next(route for route in scored if route["id"] == "calm")[
        "sensory_indicator"
    ] == LOW


def test_monitor_reports_first_threshold_breach_with_live_data():
    result = monitor_route(
        _route("route", -37.81, 10)["geometry"]["coordinates"],
        _snapshot([_sensor("high", -37.81, 700)]),
        "MEDIUM",
    )

    assert result["breached"] is True
    assert result["upcoming_peak"] == HIGH
    assert result["affected_segment_index"] == 0


def test_monitor_never_alerts_from_fallback_data():
    snapshot = _snapshot([_sensor("high", -37.81, 700)])
    snapshot["source"] = "fallback"

    result = monitor_route(
        _route("route", -37.81, 10)["geometry"]["coordinates"],
        snapshot,
        "LOW",
    )

    assert result["breached"] is False
    assert result["upcoming_peak"] == NO_DATA


def _indicator(peak, tolerance):
    return route_sensory_indicator(
        peak,
        coverage=1,
        route_source="live",
        pedestrian_source="live",
        crowd_tolerance=tolerance,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


def test_every_route_is_labelled_so_the_comparison_never_collapses():
    # One route can win on speed and on calm at once. When it did, the others
    # were left with no role and the screen showed a single option twice.
    scored, fastest_id, calmest_id, _ = score_routes(
        [
            _route("route-1", -37.8100, 12),
            _route("route-2", -37.8300, 14),
            _route("route-3", -37.8500, 16),
        ],
        _snapshot([_sensor("s1", -37.8100, 40)]),
        route_source="live",
    )

    assert fastest_id == calmest_id == "route-1"
    assert all(route["roles"] for route in scored)
    assert [route["id"] for route in scored if "Alternative" in route["roles"]] == [
        "route-2",
        "route-3",
    ]
    # Three distinct routes remain available to compare.
    assert len({route["id"] for route in scored}) == 3


def _route(route_id, latitude, duration):
    return {
        "id": route_id,
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [144.9600, latitude],
                [144.9650, latitude],
            ],
        },
        "distance_meters": 900,
        "duration_minutes": duration,
        "source": "LIVE",
        "fallback_reason": None,
        "steps": [],
    }


def _sensor(sensor_id, latitude, count, lon=144.9625):
    return {
        "id": sensor_id,
        "name": f"Sensor {sensor_id}",
        "lat": latitude,
        "lon": lon,
        "count": count,
    }


def _snapshot(sensors):
    return {
        "source": "live",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sensors": sensors,
    }


def _scored_route(route_id, level, coverage, average_load, duration):
    return {
        "id": route_id,
        "sensory_level": level,
        "coverage": coverage,
        "average_load": average_load,
        "duration_minutes": duration,
    }


def _recommendation_route(
    route_id,
    indicator,
    peak,
    coverage,
    average_load,
    duration,
):
    route = _scored_route(route_id, peak, coverage, average_load, duration)
    route["sensory_indicator"] = indicator
    return route


def test_peak_separates_the_doorstep_from_the_stretch_a_route_can_choose():
    # The only busy sensor sits on the origin, which no route can avoid.
    scored, _, _, _ = score_routes(
        [_long_route("route-1", -37.8100)],
        _snapshot([
            _sensor("origin", -37.8100, 200, lon=144.9600),
            _sensor("middle", -37.8100, 20, lon=144.9700),
        ]),
        route_source="live",
    )

    route = scored[0]
    # The trip really does reach High, and still says so.
    assert route["sensory_level"] == HIGH
    assert route["unavoidable_level"] == HIGH
    # But nothing it could have chosen differently is above Low.
    assert route["avoidable_level"] == LOW


def test_calmest_compares_the_avoidable_stretch_not_the_shared_doorstep():
    # Both routes leave past the same busy corner, so both peak High. Only the
    # middle of the trip tells them apart.
    routes = [_long_route("loud", -37.8100), _long_route("quiet", -37.8140)]
    sensors = [
        _sensor("origin-loud", -37.8100, 200, lon=144.9600),
        _sensor("origin-quiet", -37.8140, 200, lon=144.9600),
        _sensor("middle-loud", -37.8100, 200, lon=144.9700),
        _sensor("middle-quiet", -37.8140, 20, lon=144.9700),
    ]

    scored, _, calmest_id, _ = score_routes(routes, _snapshot(sensors), route_source="live")

    assert {route["sensory_level"] for route in scored} == {HIGH}
    assert calmest_id == "quiet"


def _long_route(route_id, latitude):
    """A route long enough to have blocks that are not on either doorstep."""
    return {
        "id": route_id,
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [144.9600 + step * 0.0025, latitude] for step in range(9)
            ],
        },
        "distance_meters": 1760,
        "duration_minutes": 22,
        "source": "LIVE",
        "fallback_reason": None,
        "steps": [],
    }
