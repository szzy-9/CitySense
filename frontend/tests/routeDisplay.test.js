import test from "node:test";
import assert from "node:assert/strict";

import {
  buildRouteRequest,
  buildCalmestComparison,
  canStartReroute,
  closestRouteProgress,
  compareObservedPeaks,
  formatDataStatus,
  formatLoadLevel,
  formatSensoryIndicator,
  isArrived,
  isConfirmedLocation,
  isOffRoute,
  monitorAlertSignature,
  navigationSummary,
  nextFollowMode,
  preserveCurrentRouteResult,
  remainingRouteCoordinates,
  remainingRouteDistance,
  selectCurrentRouteStep,
  shouldShowMonitorAlert,
} from "../src/routeDisplay.js";


test("No Data is displayed explicitly and never formatted as Low", () => {
  assert.equal(formatLoadLevel("NO_DATA"), "No Data");
  assert.notEqual(formatLoadLevel("NO_DATA"), formatLoadLevel("LOW"));
});

test("prototype routes are labelled clearly", () => {
  assert.equal(formatDataStatus("PROTOTYPE"), "Prototype route");
});

test("calmest comparison reports limited segment coverage", () => {
  const fastest = route("route-1", 10, "HIGH", ["HIGH"]);
  const calmest = route("route-2", 13, "MODERATE", ["MODERATE", "NO_DATA"]);

  assert.equal(
    buildCalmestComparison(fastest, calmest),
    "3 minutes longer. Observed peak is Moderate; coverage is limited.",
  );
});

test("calmest comparison does not claim calm conditions without data", () => {
  const fastest = route("route-1", 10, "NO_DATA", ["NO_DATA"]);
  const calmest = route("route-2", 12, "NO_DATA", ["NO_DATA"]);

  assert.equal(
    buildCalmestComparison(fastest, calmest),
    "Crowd data is insufficient for a reliable calmest comparison.",
  );
});

test("typed text is not a confirmed location until a result is selected", () => {
  assert.equal(isConfirmedLocation(null), false);
  assert.equal(isConfirmedLocation({ label: "Typed only" }), false);
  assert.equal(
    isConfirmedLocation({
      label: "Flinders Street Station",
      lat: -37.8183,
      lon: 144.9671,
      source: "autocomplete",
    }),
    true,
  );
});

test("off-route detection does not request or calculate a new route", () => {
  const nearLocation = {
    label: "Current Location",
    lat: -37.8175,
    lon: 144.9675,
    source: "current_location",
  };
  const farLocation = {
    label: "Current Location",
    lat: -37.81,
    lon: 144.98,
    source: "current_location",
  };
  const routeGeometry = {
    coordinates: [
      [144.967, -37.818],
      [144.968, -37.817],
    ],
  };

  assert.equal(
    isOffRoute(nearLocation, routeGeometry, 120),
    false,
  );
  assert.equal(
    isOffRoute(farLocation, routeGeometry, 120),
    true,
  );
});

test("closest route point and remaining distance advance with location", () => {
  const geometry = {
    coordinates: [
      [144.960, -37.810],
      [144.965, -37.810],
      [144.970, -37.810],
    ],
  };
  const halfway = location(144.965, -37.810);

  const progress = closestRouteProgress(halfway, geometry);
  const remaining = remainingRouteCoordinates(halfway, geometry);

  assert.equal(progress.segmentIndex, 0);
  assert.ok(progress.amount > 0.99);
  assert.equal(remaining.length, 3);
  assert.ok(remainingRouteDistance(halfway, geometry) > 400);
  assert.ok(remainingRouteDistance(halfway, geometry) < 500);
});

test("current route step and navigation summary use ORS way points", () => {
  const routeWithSteps = {
    distance_meters: 900,
    duration_minutes: 12,
    geometry: {
      coordinates: [
        [144.960, -37.810],
        [144.965, -37.810],
        [144.970, -37.810],
      ],
    },
    steps: [
      { instruction: "Walk east", way_points: [0, 1] },
      { instruction: "Continue east", way_points: [1, 2] },
    ],
  };
  const current = location(144.966, -37.810);
  const destination = {
    ...location(144.970, -37.810),
    label: "Destination",
    source: "autocomplete",
  };

  assert.equal(
    selectCurrentRouteStep(routeWithSteps, current).instruction,
    "Continue east",
  );
  const summary = navigationSummary(routeWithSteps, current, destination);
  assert.equal(summary.arrived, false);
  assert.equal(summary.step.instruction, "Continue east");
  assert.ok(summary.remainingDistance > 0);
  assert.ok(summary.distanceToNextStep > 0);
});

test("arrival detection uses a configurable distance boundary", () => {
  const destination = {
    ...location(144.970, -37.810),
    label: "Destination",
    source: "autocomplete",
  };

  assert.equal(isArrived(location(144.9701, -37.810), destination, 20), true);
  assert.equal(isArrived(location(144.971, -37.810), destination, 20), false);
});

test("follow mode pauses for manual movement and resumes on recentre", () => {
  assert.equal(nextFollowMode(true, "manual-map-move"), false);
  assert.equal(nextFollowMode(false, "recentre"), true);
  assert.equal(nextFollowMode(true, "position-update"), true);
});

test("reroute request preserves destination and crowd tolerance", () => {
  const origin = location(144.965, -37.811);
  const destination = {
    ...location(144.970, -37.810),
    label: "Confirmed destination",
    source: "autocomplete",
  };

  const request = buildRouteRequest(origin, destination, "LOW");

  assert.deepEqual(request.start, origin);
  assert.deepEqual(request.end, destination);
  assert.equal(request.crowd_tolerance, "LOW");
  assert.equal(canStartReroute(false), true);
  assert.equal(canStartReroute(true), false);
});

test("reroute outcome clearly reports when no calmer route exists", () => {
  assert.equal(
    compareObservedPeaks({ peak_load: "HIGH" }, { peak_load: "HIGH" }),
    "No lower-load alternative was found. The lowest observed option is shown.",
  );
});

test("failed reroute preserves the current route result", () => {
  const currentResult = { recommended_route_id: "route-1" };

  assert.equal(preserveCurrentRouteResult(currentResult, null), currentResult);
  assert.deepEqual(
    preserveCurrentRouteResult(currentResult, { recommended_route_id: "route-2" }),
    { recommended_route_id: "route-2" },
  );
});

test("sensory indicator has explicit text for low, high, and no data", () => {
  assert.equal(formatSensoryIndicator("LOW"), "Within your crowd limit");
  assert.equal(formatSensoryIndicator("HIGH"), "Above your crowd limit");
  assert.equal(formatSensoryIndicator("NO_DATA"), "Not enough reliable data");
  assert.notEqual(formatSensoryIndicator("NO_DATA"), formatSensoryIndicator("LOW"));
});

test("active-route monitoring suppresses an identical repeated alert", () => {
  const response = {
    breached: true,
    upcoming_peak: "HIGH",
    affected_segment_index: 3,
  };
  const signature = monitorAlertSignature(response);

  assert.equal(signature, "HIGH:3");
  assert.equal(shouldShowMonitorAlert(response, ""), true);
  assert.equal(shouldShowMonitorAlert(response, signature), false);
  assert.equal(
    shouldShowMonitorAlert({ ...response, breached: false }, signature),
    false,
  );
});

function route(id, duration, sensoryLevel, levels) {
  return {
    id,
    duration_minutes: duration,
    sensory_level: sensoryLevel,
    segments: levels.map((level, index) => ({
      id: `segment-${index + 1}`,
      sensory_level: level,
    })),
  };
}

function location(lon, lat) {
  return {
    label: "Current Location",
    lon,
    lat,
    source: "current_location",
  };
}
