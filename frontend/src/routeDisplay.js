const LOAD_LABELS = {
  LOW: "Low",
  MODERATE: "Moderate",
  HIGH: "High",
  NO_DATA: "No Data",
};

const INDICATOR_LABELS = {
  LOW: "Within your crowd limit",
  HIGH: "Above your crowd limit",
  NO_DATA: "Not enough reliable data",
};

const DATA_STATUS_LABELS = {
  LIVE: "Live data",
  FALLBACK: "Sample data",
  PROTOTYPE: "Example route",
  NO_DATA: "No data",
};

// Internal source enums must never reach the screen as raw values.
const SOURCE_LABELS = {
  DATABASE: "imported",
  LIVE_API: "live from the city",
  FALLBACK: "sample data",
  CURATED_PROTOTYPE: "our own shortlist",
  NO_DATA: "none yet",
};

const LOAD_RANK = {
  LOW: 1,
  MODERATE: 2,
  HIGH: 3,
};

export function formatLoadLevel(level) {
  return LOAD_LABELS[level] || "No Data";
}

export function formatSensoryIndicator(indicator) {
  return INDICATOR_LABELS[indicator] || INDICATOR_LABELS.NO_DATA;
}

export function formatDataStatus(status) {
  return DATA_STATUS_LABELS[status] || "No data";
}

export function formatSourceLabel(source) {
  return SOURCE_LABELS[source] || SOURCE_LABELS.NO_DATA;
}

const CONFIDENCE_LABELS = {
  HIGH: "We are confident",
  MEDIUM: "Fairly confident",
  LOW: "Less confident",
};

export function formatConfidence(confidence) {
  return CONFIDENCE_LABELS[confidence] || CONFIDENCE_LABELS.LOW;
}

export function buildCalmestComparison(fastest, calmest) {
  if (!fastest || !calmest) {
    return "";
  }

  if (fastest.id === calmest.id) {
    return "This route is both the fastest and the calmest we can find.";
  }

  if (calmest.sensory_level === "NO_DATA") {
    return "We do not have enough crowd data to compare these routes.";
  }

  const difference = Math.max(
    0,
    Math.round(calmest.duration_minutes - fastest.duration_minutes),
  );
  const timeText = difference === 1 ? "1 minute longer" : `${difference} minutes longer`;
  const segments = calmest.segments || [];
  const hasMissingData = segments.some(
    (segment) => segment.sensory_level === "NO_DATA",
  );
  const level = formatLoadLevel(calmest.sensory_level);

  if (hasMissingData) {
    return `${timeText}. Reaches ${level} at its busiest, and part of it has no sensors.`;
  }

  return `${timeText}, and nothing along it goes above ${level}.`;
}

export function isConfirmedLocation(location) {
  return Boolean(
    location &&
      typeof location.label === "string" &&
      location.label.trim() &&
      Number.isFinite(location.lat) &&
      Number.isFinite(location.lon) &&
      typeof location.source === "string" &&
      location.source,
  );
}

export function buildRouteRequest(
  origin,
  destination,
  crowdTolerance,
  departureTime = null,
) {
  const request = {
    start: { ...origin },
    end: { ...destination },
    crowd_tolerance: crowdTolerance,
  };
  if (departureTime) {
    request.departure_time = departureTime;
  }
  return request;
}

export function toTimezoneAwareDeparture(value) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

export function selectRouteDeparture(inputValue, preservedValue = null) {
  return toTimezoneAwareDeparture(inputValue) || preservedValue || null;
}

export function canStartReroute(rerouteInProgress) {
  return !rerouteInProgress;
}

export function preserveCurrentRouteResult(currentResult, nextResult) {
  return nextResult || currentResult;
}

export function isOffRoute(location, geometry, thresholdMetres = 120) {
  const progress = closestRouteProgress(location, geometry);
  return progress ? progress.distanceToRoute > thresholdMetres : false;
}

export function closestRouteProgress(location, geometry) {
  if (
    !isConfirmedLocation(location) ||
    !geometry ||
    !Array.isArray(geometry.coordinates) ||
    geometry.coordinates.length < 2
  ) {
    return null;
  }

  let closest = null;
  for (let index = 0; index < geometry.coordinates.length - 1; index += 1) {
    const projection = projectToSegment(
      location,
      geometry.coordinates[index],
      geometry.coordinates[index + 1],
    );
    if (!closest || projection.distance < closest.distanceToRoute) {
      closest = {
        segmentIndex: index,
        amount: projection.amount,
        distanceToRoute: projection.distance,
        projectedCoordinate: projection.coordinate,
      };
    }
  }
  return closest;
}

export function remainingRouteCoordinates(location, geometry, maximumPoints = 500) {
  const coordinates = geometry?.coordinates;
  if (!Array.isArray(coordinates) || coordinates.length < 2) {
    return [];
  }

  const progress = closestRouteProgress(location, geometry);
  const remaining = progress
    ? [progress.projectedCoordinate, ...coordinates.slice(progress.segmentIndex + 1)]
    : [...coordinates];
  return limitCoordinates(remaining, maximumPoints);
}

export function remainingRouteDistance(location, geometry) {
  return lineDistance(remainingRouteCoordinates(location, geometry));
}

export function selectCurrentRouteStep(route, location) {
  const steps = route?.steps || [];
  if (!steps.length) {
    return null;
  }
  const progress = closestRouteProgress(location, route.geometry);
  if (!progress) {
    return steps[0];
  }

  const currentCoordinateIndex = progress.segmentIndex + progress.amount;
  return (
    steps.find((step) => step.way_points?.[1] >= currentCoordinateIndex) ||
    steps[steps.length - 1]
  );
}

export function navigationSummary(route, location, destination, arrivalMetres = 35) {
  if (!route) {
    return null;
  }

  const arrived = isArrived(location, destination, arrivalMetres);
  const remainingDistance = arrived
    ? 0
    : Math.round(remainingRouteDistance(location, route.geometry));
  const totalDistance = Math.max(1, Number(route.distance_meters) || 1);
  const remainingMinutes = Math.max(
    0,
    Math.round((Number(route.duration_minutes) || 0) * (remainingDistance / totalDistance)),
  );
  const step = selectCurrentRouteStep(route, location);
  const stepDistance = step
    ? distanceToStepEnd(location, route.geometry, step)
    : null;

  return {
    arrived,
    step,
    distanceToNextStep: stepDistance,
    remainingDistance,
    remainingMinutes,
  };
}

export function isArrived(location, destination, thresholdMetres = 35) {
  if (!isConfirmedLocation(location) || !isConfirmedLocation(destination)) {
    return false;
  }
  return haversineDistanceMeters(
    [location.lon, location.lat],
    [destination.lon, destination.lat],
  ) <= thresholdMetres;
}

export function nextFollowMode(currentValue, event) {
  if (event === "manual-map-move") {
    return false;
  }
  if (event === "recentre") {
    return true;
  }
  return currentValue;
}

export function compareObservedPeaks(previousRoute, nextRoute) {
  const previousRank = LOAD_RANK[previousRoute?.peak_load] || Infinity;
  const nextRank = LOAD_RANK[nextRoute?.peak_load] || Infinity;
  if (!Number.isFinite(nextRank)) {
    return "We cannot check crowds on that alternative right now.";
  }
  if (!Number.isFinite(previousRank) || nextRank < previousRank) {
    return "There is a calmer way to go.";
  }
  return "Nothing calmer nearby. This is the calmest option we found.";
}

export function monitorAlertSignature(response) {
  if (!response?.breached) {
    return "";
  }
  return `${response.upcoming_peak}:${response.affected_segment_index}`;
}

export function shouldShowMonitorAlert(response, previousSignature) {
  const signature = monitorAlertSignature(response);
  return Boolean(signature && signature !== previousSignature);
}

export function haversineDistanceMeters(pointA, pointB) {
  const [lonA, latA] = pointA;
  const [lonB, latB] = pointB;
  const earthRadius = 6_371_000;
  const latitudeChange = radians(latB - latA);
  const longitudeChange = radians(lonB - lonA);
  const value =
    Math.sin(latitudeChange / 2) ** 2 +
    Math.cos(radians(latA)) *
      Math.cos(radians(latB)) *
      Math.sin(longitudeChange / 2) ** 2;
  return earthRadius * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
}

function distanceToStepEnd(location, geometry, step) {
  if (!isConfirmedLocation(location) || !step?.way_points) {
    return null;
  }
  const endIndex = step.way_points[1];
  const progress = closestRouteProgress(location, geometry);
  if (!progress || endIndex < progress.segmentIndex) {
    return 0;
  }
  const coordinates = [
    progress.projectedCoordinate,
    ...geometry.coordinates.slice(progress.segmentIndex + 1, endIndex + 1),
  ];
  return Math.round(lineDistance(coordinates));
}

function projectToSegment(location, start, end) {
  const latitudeRadians = radians(location.lat);
  const metresPerLongitudeDegree = 111_320 * Math.cos(latitudeRadians);
  const metresPerLatitudeDegree = 110_540;
  const startX = (start[0] - location.lon) * metresPerLongitudeDegree;
  const startY = (start[1] - location.lat) * metresPerLatitudeDegree;
  const endX = (end[0] - location.lon) * metresPerLongitudeDegree;
  const endY = (end[1] - location.lat) * metresPerLatitudeDegree;
  const segmentX = endX - startX;
  const segmentY = endY - startY;
  const segmentLengthSquared = segmentX * segmentX + segmentY * segmentY;
  const amount = segmentLengthSquared
    ? Math.max(
        0,
        Math.min(1, -(startX * segmentX + startY * segmentY) / segmentLengthSquared),
      )
    : 0;

  return {
    amount,
    distance: Math.hypot(startX + amount * segmentX, startY + amount * segmentY),
    coordinate: [
      start[0] + (end[0] - start[0]) * amount,
      start[1] + (end[1] - start[1]) * amount,
    ],
  };
}

function lineDistance(coordinates) {
  let distance = 0;
  for (let index = 0; index < coordinates.length - 1; index += 1) {
    distance += haversineDistanceMeters(coordinates[index], coordinates[index + 1]);
  }
  return distance;
}

function limitCoordinates(coordinates, maximumPoints) {
  if (coordinates.length <= maximumPoints) {
    return coordinates;
  }
  const limited = [];
  for (let index = 0; index < maximumPoints; index += 1) {
    const sourceIndex = Math.round(
      (index * (coordinates.length - 1)) / (maximumPoints - 1),
    );
    limited.push(coordinates[sourceIndex]);
  }
  return limited;
}

function radians(value) {
  return (value * Math.PI) / 180;
}
