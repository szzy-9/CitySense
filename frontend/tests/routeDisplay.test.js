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
  destinationAlertSignature,
  predictiveAlertSignature,
  preserveCurrentRouteResult,
  remainingRouteCoordinates,
  remainingRouteDistance,
  segmentsAheadOfLocation,
  selectCurrentRouteStep,
  selectDestinationAlert,
  selectPredictiveAlert,
  selectRouteDeparture,
  shouldShowDestinationAlert,
  shouldShowMonitorAlert,
  shouldShowPredictiveAlert,
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

/*
 * A four-block walk due east, forty minutes end to end, so each block is ten
 * minutes and a position on a block boundary lands on a round lead time. The
 * third block is the one historical patterns call busy.
 */
const PREDICTED_ROUTE_LONGITUDES = [144.96, 144.961, 144.962, 144.963, 144.964];

function predictedRoute(overrides = {}) {
  const coordinates = PREDICTED_ROUTE_LONGITUDES.map((lon) => [lon, -37.81]);
  const bands = overrides.bands || ["LOW", "LOW", "HIGH", "LOW"];
  const confidences = overrides.confidences || ["HIGH", "HIGH", "HIGH", "HIGH"];

  return {
    id: "route-1",
    route_source: overrides.route_source || "live",
    duration_minutes: overrides.duration_minutes || 40,
    geometry: { type: "LineString", coordinates },
    segments: bands.map((band, index) => ({
      id: `segment-${index + 1}`,
      geometry: {
        type: "LineString",
        coordinates: coordinates.slice(index, index + 2),
      },
      historical_prediction_available: true,
      predicted_band: band,
      prediction_confidence: confidences[index],
      predicted_for: overrides.predicted_for || null,
    })),
  };
}

test("stretches already walked past drop out of the ones still ahead", () => {
  // Standing on the first boundary: a quarter of the walk is behind, and the
  // busy third block is ten minutes off.
  const ahead = segmentsAheadOfLocation(predictedRoute(), location(144.961, -37.81));

  assert.deepEqual(
    ahead.map((item) => item.index),
    [1, 2, 3],
  );
  assert.equal(Math.round(ahead[1].etaMinutes), 10);
});

test("a predicted busy stretch is flagged before the walker reaches it", () => {
  const alert = selectPredictiveAlert(
    predictedRoute(),
    location(144.961, -37.81),
    "MEDIUM",
  );

  assert.equal(alert.predicted_condition, "HIGH");
  assert.equal(alert.segment_index, 2);
  assert.equal(alert.lead_minutes, 10);
  assert.equal(alert.confidence, "HIGH");
  assert.equal(alert.pattern_hour_drift, false);
  assert.match(alert.message, /Likely high in about 10 minutes/);
  // Internal band names must never reach the screen.
  assert.doesNotMatch(alert.message, /HIGH|NO_DATA/);
});

test("the warning stops once the busy stretch is behind the walker", () => {
  // Seven eighths of the way along: the third block has been walked.
  const alert = selectPredictiveAlert(
    predictedRoute(),
    location(144.9635, -37.81),
    "MEDIUM",
  );

  assert.equal(alert, null);
});

test("a stretch the walker is already inside is no longer a warning ahead", () => {
  // Six tenths along: the busy third block has been entered but not finished.
  const alert = selectPredictiveAlert(
    predictedRoute(),
    location(144.9624, -37.81),
    "MEDIUM",
  );

  assert.equal(alert, null);
});

test("nothing new is raised inside the last few minutes, but a shown alert counts down", () => {
  const nearly = location(144.9619, -37.81);

  assert.equal(selectPredictiveAlert(predictedRoute(), nearly, "MEDIUM"), null);

  const stillShowing = selectPredictiveAlert(predictedRoute(), nearly, "MEDIUM", {
    raisedSignature: "2:HIGH",
  });

  assert.equal(stillShowing.lead_minutes, 1);
  assert.match(stillShowing.message, /about a minute/);
});

test("a stretch further off than an hour is not called yet", () => {
  const alert = selectPredictiveAlert(
    predictedRoute({ duration_minutes: 400 }),
    location(144.96, -37.81),
    "MEDIUM",
  );

  assert.equal(alert, null);
});

test("no warning when the outlook sits inside the walker's own crowd limit", () => {
  assert.equal(
    selectPredictiveAlert(predictedRoute(), location(144.961, -37.81), "HIGH"),
    null,
  );
});

test("a thin historical pattern is not worth interrupting someone over", () => {
  const route = predictedRoute({
    confidences: ["HIGH", "HIGH", "LOW", "HIGH"],
  });

  assert.equal(
    selectPredictiveAlert(route, location(144.961, -37.81), "MEDIUM"),
    null,
  );
});

test("an example route never produces a forecast", () => {
  const route = predictedRoute({ route_source: "fallback" });

  assert.equal(
    selectPredictiveAlert(route, location(144.961, -37.81), "MEDIUM"),
    null,
  );
});

test("a trip running into a different hour says which pattern it is reading", () => {
  const now = new Date(2026, 7, 4, 8, 30);
  const route = predictedRoute({
    predicted_for: new Date(2026, 7, 4, 9, 0).toISOString(),
  });

  const alert = selectPredictiveAlert(route, location(144.961, -37.81), "MEDIUM", {
    now: now.getTime(),
  });

  assert.equal(alert.pattern_hour_drift, true);
  assert.match(alert.message, /9am pattern/);
  assert.match(alert.message, /around 8am/);
  assert.match(alert.message, /check another route/);
});

test("dismissing a predicted-crowding warning keeps it dismissed", () => {
  const alert = selectPredictiveAlert(
    predictedRoute(),
    location(144.961, -37.81),
    "MEDIUM",
  );
  const signature = predictiveAlertSignature(alert);

  assert.equal(signature, "2:HIGH");
  assert.equal(shouldShowPredictiveAlert(alert, ""), true);
  assert.equal(shouldShowPredictiveAlert(alert, signature), false);
  assert.equal(shouldShowPredictiveAlert(null, ""), false);
});

/*
 * The same four-block walk, but the busy block is the last one: the walker's
 * destination rather than somewhere they pass through. AC 2.2a and AC 2.2b ask
 * for a warning before arrival with enough lead time to act, and the acting
 * here cannot be a reroute.
 */
function destinationRoute(overrides = {}) {
  return predictedRoute({
    bands: ["LOW", "LOW", "LOW", "HIGH"],
    ...overrides,
  });
}

test("a busy destination is named while the trip can still be delayed", () => {
  const alert = selectDestinationAlert(destinationRoute(), "MEDIUM", {
    now: new Date(2026, 7, 4, 8, 0).getTime(),
  });

  assert.equal(alert.predicted_condition, "HIGH");
  assert.equal(alert.phase, "planning");
  assert.equal(alert.lead_minutes, 40);
  assert.equal(alert.arrival_label, "8am");
  assert.match(alert.message, /Near your destination is likely high/);
  assert.match(alert.message, /around the time you get there \(8am\)/);
  assert.doesNotMatch(alert.message, /HIGH|NO_DATA/);
});

test("the destination warning counts down to arrival while walking", () => {
  const alert = selectDestinationAlert(destinationRoute(), "MEDIUM", {
    phase: "approach",
    remainingMinutes: 12,
  });

  assert.equal(alert.phase, "approach");
  assert.equal(alert.lead_minutes, 12);
  assert.match(alert.message, /when you arrive, in about 12 minutes/);
});

test("on approach the warning waits until arrival is close enough to act on", () => {
  // Half an hour out, a walker is being told about a place they already chose.
  assert.equal(
    selectDestinationAlert(destinationRoute(), "MEDIUM", {
      phase: "approach",
      remainingMinutes: 30,
    }),
    null,
  );

  assert.notEqual(
    selectDestinationAlert(destinationRoute(), "MEDIUM", {
      phase: "approach",
      remainingMinutes: 15,
    }),
    null,
  );
});

test("a walk longer than the hour the pattern covers raises nothing", () => {
  assert.equal(
    selectDestinationAlert(destinationRoute({ duration_minutes: 400 }), "MEDIUM"),
    null,
  );
});

test("the destination warning stops once the walker has arrived", () => {
  assert.equal(
    selectDestinationAlert(destinationRoute(), "MEDIUM", {
      phase: "approach",
      remainingMinutes: 1,
      arrived: true,
    }),
    null,
  );
});

test("a destination inside the walker's own limit is not warned about", () => {
  assert.equal(selectDestinationAlert(destinationRoute(), "HIGH"), null);
});

test("a thin pattern for the destination is not worth interrupting over", () => {
  const route = destinationRoute({
    confidences: ["HIGH", "HIGH", "HIGH", "LOW"],
  });

  assert.equal(selectDestinationAlert(route, "MEDIUM"), null);
});

test("an example route never forecasts the destination either", () => {
  assert.equal(
    selectDestinationAlert(destinationRoute({ route_source: "fallback" }), "MEDIUM"),
    null,
  );
});

test("an unavoidable destination says so, rather than implying a reroute", () => {
  const route = destinationRoute();
  route.congestion_avoidable = false;

  const alert = selectDestinationAlert(route, "MEDIUM");

  assert.equal(alert.avoidable, false);
  assert.match(alert.message, /No route avoids it\./);
});

test("the destination owns the last stretch, so only one warning is raised", () => {
  const route = destinationRoute();
  const standingAtTheStart = location(144.96, -37.81);

  // Without the exclusion the same block would produce a second warning, one
  // that offers a reroute the walker cannot use.
  assert.equal(
    selectPredictiveAlert(route, standingAtTheStart, "MEDIUM").segment_index,
    3,
  );
  assert.equal(
    selectPredictiveAlert(route, standingAtTheStart, "MEDIUM", {
      excludeFinalSegment: true,
    }),
    null,
  );
  assert.equal(selectDestinationAlert(route, "MEDIUM").segment_index, 3);
});

test("a trip planned for a later hour arrives in that hour, not this one", () => {
  // Planned at 2am for a 5pm departure. Reading the arrival off the clock said
  // "due there around 2am" and then called the 5pm pattern the wrong one.
  const planningNow = new Date(2026, 7, 12, 2, 0);
  const departure = new Date(2026, 7, 14, 17, 0);
  const route = destinationRoute({
    duration_minutes: 16,
    predicted_for: new Date(2026, 7, 14, 17, 16).toISOString(),
  });

  const alert = selectDestinationAlert(route, "MEDIUM", {
    now: planningNow.getTime(),
    departureIso: departure.toISOString(),
  });

  assert.equal(alert.arrival_label, "5pm");
  assert.match(alert.message, /around the time you get there \(5pm\)/);
  assert.doesNotMatch(alert.message, /2am/);
  assert.doesNotMatch(alert.message, /pattern, but you are now due/);
});

test("without a planned departure the walker is leaving now", () => {
  const now = new Date(2026, 7, 12, 9, 0);
  const alert = selectDestinationAlert(destinationRoute({ duration_minutes: 40 }), "MEDIUM", {
    now: now.getTime(),
  });

  assert.equal(alert.arrival_label, "9am");
});

test("waving the warning away at planning does not waive it on approach", () => {
  const planning = selectDestinationAlert(destinationRoute(), "MEDIUM");
  const approaching = selectDestinationAlert(destinationRoute(), "MEDIUM", {
    phase: "approach",
    remainingMinutes: 8,
  });
  const dismissed = destinationAlertSignature(planning);

  assert.equal(dismissed, "destination:planning:HIGH");
  assert.equal(shouldShowDestinationAlert(planning, dismissed), false);
  assert.equal(shouldShowDestinationAlert(approaching, dismissed), true);
  assert.equal(shouldShowDestinationAlert(null, ""), false);
});
