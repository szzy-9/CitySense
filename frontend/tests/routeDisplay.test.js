import test from "node:test";
import assert from "node:assert/strict";

import {
  buildRouteRequest,
  buildCalmestComparison,
  canStartReroute,
  closestRouteProgress,
  compareObservedPeaks,
  formatDataStatus,
  describeUnavoidablePeak,
  formatLoadLevel,
  formatRouteRoles,
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
  selectRouteDeparture,
  shouldShowMonitorAlert,
  toTimezoneAwareDeparture,
} from "../src/routeDisplay.js";
import { UserFacingError, messageForError } from "../src/userMessages.js";


test("raw network exceptions never reach the user", () => {
  // A failed fetch throws exactly this, and it used to be shown on screen.
  const networkFailure = new TypeError("Failed to fetch");
  const shown = messageForError(networkFailure, "Please try again shortly.");

  assert.equal(shown, "Please try again shortly.");
  assert.doesNotMatch(shown, /Failed to fetch/);
});

test("messages written for people are shown as they were written", () => {
  const written = new UserFacingError("We could not find that address.");

  assert.equal(
    messageForError(written, "Please try again shortly."),
    "We could not find that address.",
  );
});


test("No Data is displayed explicitly and never formatted as Low", () => {
  assert.equal(formatLoadLevel("NO_DATA"), "No Data");
  assert.notEqual(formatLoadLevel("NO_DATA"), formatLoadLevel("LOW"));
});

test("prototype routes are labelled clearly", () => {
  assert.equal(formatDataStatus("PROTOTYPE"), "Example route");
});

test("calmest comparison reports limited segment coverage", () => {
  const fastest = route("route-1", 10, "HIGH", ["HIGH"]);
  const calmest = route("route-2", 13, "MODERATE", ["MODERATE", "NO_DATA"]);

  assert.equal(
    buildCalmestComparison(fastest, calmest),
    "3 minutes longer. Reaches Moderate at its busiest, and part of it has no sensors.",
  );
});

test("calmest comparison does not claim calm conditions without data", () => {
  const fastest = route("route-1", 10, "NO_DATA", ["NO_DATA"]);
  const calmest = route("route-2", 12, "NO_DATA", ["NO_DATA"]);

  assert.equal(
    buildCalmestComparison(fastest, calmest),
    "We do not have enough crowd data to compare these routes.",
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

  const departure = "2026-08-06T00:30:00.000Z";
  const request = buildRouteRequest(origin, destination, "LOW", departure);

  assert.deepEqual(request.start, origin);
  assert.deepEqual(request.end, destination);
  assert.equal(request.crowd_tolerance, "LOW");
  assert.equal(request.departure_time, departure);
  assert.equal(canStartReroute(false), true);
  assert.equal(canStartReroute(true), false);
});

test("a datetime-local value is converted to a timezone-aware ISO timestamp", () => {
  const departure = toTimezoneAwareDeparture("2026-08-06T09:30");

  assert.match(departure, /^2026-08-\d{2}T\d{2}:30:00\.000Z$/);
  assert.equal(toTimezoneAwareDeparture(""), null);
});

test("departure time remains part of a reroute request", () => {
  const departure = "2026-08-06T00:30:00.000Z";
  const reroute = buildRouteRequest(
    location(144.966, -37.811),
    { ...location(144.970, -37.810), label: "Destination" },
    "MEDIUM",
    departure,
  );

  assert.equal(reroute.start.source, "current_location");
  assert.equal(reroute.departure_time, departure);
});

test("a backend-defaulted departure time is preserved for rerouting", () => {
  const preserved = "2026-08-06T09:30:00+10:00";

  assert.equal(selectRouteDeparture("", preserved), preserved);
});

test("reroute outcome clearly reports when no calmer route exists", () => {
  assert.equal(
    compareObservedPeaks({ peak_load: "HIGH" }, { peak_load: "HIGH" }),
    "Nothing calmer nearby. This is the calmest option we found.",
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
  assert.equal(formatSensoryIndicator("NO_DATA"), "Not enough data");
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

test("route role labels read as a sentence and leave the recommended badge alone", () => {
  assert.equal(formatRouteRoles(["Fastest"]), "Fastest");
  assert.equal(formatRouteRoles(["Fastest", "Calmest"]), "Fastest and Calmest");
  assert.equal(
    formatRouteRoles(["Fastest", "Calmest", "Recommended"]),
    "Fastest and Calmest",
  );
  assert.equal(formatRouteRoles(["Recommended"]), "Selected");
  assert.equal(formatRouteRoles([]), "Selected");
  assert.equal(formatRouteRoles(undefined), "Selected");
});

test("the doorstep is reported apart from the stretch a route could choose", () => {
  assert.equal(
    describeUnavoidablePeak({
      sensory_level: "HIGH",
      unavoidable_level: "HIGH",
      avoidable_level: "LOW",
    }),
    "High near the start and end, which no route avoids. Nothing above low in between.",
  );

  // Nothing to explain when the worst point is one the route actually chose.
  assert.equal(
    describeUnavoidablePeak({
      sensory_level: "HIGH",
      unavoidable_level: "LOW",
      avoidable_level: "HIGH",
    }),
    "",
  );
  assert.equal(describeUnavoidablePeak({}), "");
  assert.match(
    describeUnavoidablePeak({ unavoidable_level: "HIGH", avoidable_level: "NO_DATA" }),
    /no crowd data for the rest/,
  );
});
