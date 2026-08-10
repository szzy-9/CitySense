<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import BandIcon from "./components/BandIcon.vue";
import DataStatus from "./components/DataStatus.vue";
import LocationSearch from "./components/LocationSearch.vue";
import MapView from "./components/MapView.vue";
import OverwhelmMode from "./components/OverwhelmMode.vue";
import RefugeFinder from "./components/RefugeFinder.vue";
import RouteCard from "./components/RouteCard.vue";
import { apiUrl } from "./services/api.js";
import {
  clearWatch,
  demoLocationOrigin,
  getCurrentPosition,
  isDemoLocationActive,
  isLocationSupported,
  setDemoLocationEnabled,
  watchPosition,
} from "./services/location.js";
import {
  buildRouteRequest,
  buildCalmestComparison,
  canStartReroute,
  compareObservedPeaks,
  formatConfidence,
  formatLoadLevel,
  formatRouteRoles,
  isConfirmedLocation,
  isOffRoute,
  monitorAlertSignature,
  navigationSummary,
  predictiveAlertSignature,
  preserveCurrentRouteResult,
  remainingRouteCoordinates,
  selectPredictiveAlert,
  shouldShowMonitorAlert,
  shouldShowPredictiveAlert,
  selectRouteDeparture,
  toDateTimeLocalValue,
} from "./routeDisplay.js";
import { UserFacingError, messageForError } from "./userMessages.js";

const THEME_KEY = "citysense.theme";
const LOAD_LEVELS = ["LOW", "MODERATE", "HIGH", "NO_DATA"];

const theme = ref("dark");
const demoLocation = ref(isDemoLocationActive());
const startLocation = ref(null);
const endLocation = ref(null);
const currentLocation = ref(null);
const currentAccuracy = ref(null);
const departureTime = ref("");
const routeDepartureIso = ref("");
const crowdToleranceValue = ref(2);
const result = ref(null);
const selectedRouteId = ref("");
const refuges = ref([]);
const refugeResponse = ref(null);
const currentScreen = ref("plan");
const previousScreen = ref("plan");
const loading = ref(false);
const rerouteLoading = ref(false);
const locating = ref(false);
const refugeLoading = ref(false);
const errorMessage = ref("");
const positionMessage = ref("");
const rerouteMessage = ref("");
const rerouteTiming = ref(null);
const monitorAlert = ref(null);
const dismissedPredictiveSignature = ref("");
const raisedPredictiveSignature = ref("");
// A walker who has stopped moving sends no position updates, so the countdown
// on a predicted-crowding warning needs a clock of its own to stay honest.
const navigationClock = ref(Date.now());
const pendingAlternative = ref(null);
const alternativeLoading = ref(false);
const showLocationSimulator = import.meta.env.DEV;
const arrivalDistanceMetres = Number(
  import.meta.env.VITE_ARRIVAL_DISTANCE_METERS || 35,
);
let geolocationWatchId = null;
let geolocationWatchStarting = false;
let locationTrackingRequested = false;
let monitoringIntervalId = null;
let monitoringInFlight = false;
let monitoringController = null;
let lastMonitorAlertSignature = "";
let alternativePreparedForSignature = "";
let simulatorIndex = 0;

const fastestRoute = computed(() => {
  return result.value?.routes.find((route) => route.roles.includes("Fastest")) || null;
});

const calmestRoute = computed(() => {
  return result.value?.routes.find((route) => route.roles.includes("Calmest")) || null;
});

const recommendedRoute = computed(() => {
  return (
    result.value?.routes.find((route) => route.recommended) ||
    result.value?.routes.find(
      (route) => route.id === result.value?.recommended_route_id,
    ) ||
    calmestRoute.value ||
    fastestRoute.value
  );
});

const selectedRoute = computed(() => {
  return (
    result.value?.routes.find((route) => route.id === selectedRouteId.value) ||
    recommendedRoute.value
  );
});

const crowdTolerance = computed(() => {
  return ["LOW", "MEDIUM", "HIGH"][crowdToleranceValue.value - 1];
});

const crowdToleranceLabel = computed(() => {
  return crowdTolerance.value[0] + crowdTolerance.value.slice(1).toLowerCase();
});

// Shortest first, then the longer and calmer ones. Every route the backend
// scored is offered, so the comparison never collapses to a single card when
// one route happens to win on both counts.
const comparedRoutes = computed(() => {
  return [...(result.value?.routes || [])].sort(
    (first, second) => first.duration_minutes - second.duration_minutes,
  );
});

// When every route crosses the same busy corner, no rerouting helps. Waiting
// can, so the one departure that clears it is offered as a choice.
const departureSuggestion = computed(() => result.value?.departure_suggestion || null);

const suggestedDepartureLabel = computed(() => {
  const suggestion = departureSuggestion.value;
  if (!suggestion) {
    return "";
  }
  const date = new Date(suggestion.departure_time);
  return Number.isNaN(date.getTime())
    ? ""
    : new Intl.DateTimeFormat("en-AU", { timeStyle: "short" }).format(date);
});

async function useSuggestedDeparture() {
  const suggestion = departureSuggestion.value;
  if (!suggestion) {
    return;
  }
  departureTime.value = toDateTimeLocalValue(suggestion.departure_time);
  routeDepartureIso.value = "";
  await requestRoutes();
}

function comparisonFor(route) {
  return route.id === fastestRoute.value?.id
    ? ""
    : buildCalmestComparison(fastestRoute.value, route);
}

const offRoute = computed(() => {
  return isOffRoute(currentLocation.value, selectedRoute.value?.geometry, 120);
});

const navigation = computed(() => {
  return navigationSummary(
    selectedRoute.value,
    currentLocation.value,
    result.value?.end,
    arrivalDistanceMetres,
  );
});

/*
 * The historical outlook for the stretch the walker is heading into, read
 * against where they are now rather than where they set off from. The backend
 * states each stretch's outlook once, at planning time; recomputing which
 * stretch is still ahead is what keeps the warning ahead of the walker and
 * takes it down once the stretch is behind them.
 */
const predictiveAlert = computed(() => {
  const alert = selectPredictiveAlert(
    selectedRoute.value,
    currentLocation.value,
    crowdTolerance.value,
    {
      now: navigationClock.value,
      raisedSignature: raisedPredictiveSignature.value,
    },
  );
  return shouldShowPredictiveAlert(alert, dismissedPredictiveSignature.value)
    ? alert
    : null;
});

// A warning already on screen is allowed to keep counting down inside the last
// few minutes, so this records which one is showing.
watch(predictiveAlert, (alert) => {
  raisedPredictiveSignature.value = predictiveAlertSignature(alert);
});

function dismissPredictiveAlert() {
  dismissedPredictiveSignature.value = predictiveAlertSignature(predictiveAlert.value);
}

const canFindRoutes = computed(() => {
  return (
    isConfirmedLocation(startLocation.value) &&
    isConfirmedLocation(endLocation.value) &&
    !loading.value
  );
});

// A stand-in position is never allowed to pass as a real one.
const demoLocationNotice = computed(() => {
  if (!demoLocation.value) {
    return "";
  }
  const point = demoLocationOrigin();
  return (
    "Demo Mode is on. CitySense is reporting a fixed position at " +
    `${point.latitude.toFixed(4)}, ${point.longitude.toFixed(4)}, not reading this device.`
  );
});

/*
 * Turning Demo Mode on or off invalidates any position already on screen, so
 * the tracked position is dropped and, if a trip is underway, the watch is
 * restarted against whichever source now applies.
 */
async function toggleDemoLocation() {
  demoLocation.value = setDemoLocationEnabled(!demoLocation.value);
  errorMessage.value = "";
  currentLocation.value = null;
  currentAccuracy.value = null;
  positionMessage.value = demoLocation.value
    ? "Demo Mode is on. Positions come from a fixed CBD point."
    : "Demo Mode is off. Positions come from this device again.";

  await stopLocationTracking();
  if (currentScreen.value === "navigate") {
    await startLocationTracking();
  }
}

const routeChoices = computed(() => {
  const routes = comparedRoutes.value;
  if (routes.length < 2) {
    return [];
  }
  return routes.map((route) => ({
    id: route.id,
    role: formatRouteRoles(route.roles, "Alternative"),
    minutes: route.duration_minutes,
  }));
});

onMounted(async () => {
  applyTheme(readStoredTheme());
  await loadRefuges();
});

function readStoredTheme() {
  try {
    return window.localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
  } catch {
    // Private browsing can refuse storage. Dark is the default either way.
    return "dark";
  }
}

function applyTheme(nextTheme) {
  theme.value = nextTheme;
  document.documentElement.dataset.theme = nextTheme;
  try {
    window.localStorage.setItem(THEME_KEY, nextTheme);
  } catch {
    // The choice simply does not survive a reload. Nothing else depends on it.
  }
}

function toggleTheme() {
  applyTheme(theme.value === "dark" ? "light" : "dark");
}

onBeforeUnmount(() => {
  void stopLocationTracking();
  stopRouteMonitoring();
});

async function loadRefuges() {
  try {
    const response = await fetch(apiUrl("/api/refuges"));
    if (!response.ok) {
      throw new Error();
    }
    const body = await response.json();
    refuges.value = body.refuges;
  } catch {
    refuges.value = [];
  }
}

function setStartLocation(location) {
  startLocation.value = location;
  routeDepartureIso.value = "";
  result.value = null;
  selectedRouteId.value = "";
}

function setEndLocation(location) {
  endLocation.value = location;
  routeDepartureIso.value = "";
  result.value = null;
  selectedRouteId.value = "";
}

async function useCurrentLocation() {
  errorMessage.value = "";
  if (!isLocationSupported()) {
    errorMessage.value = "Current Location is not supported by this browser.";
    return;
  }

  locating.value = true;
  try {
    const position = await getCurrentPosition({
      enableHighAccuracy: false,
      timeout: 10000,
      maximumAge: 30000,
    });
    const location = locationFromPosition(position, "current_location");
    currentLocation.value = location;
    currentAccuracy.value = readPositionAccuracy(position);
    setStartLocation(location);
  } catch {
    errorMessage.value = "Current Location was not available. Search for an address instead.";
  } finally {
    locating.value = false;
  }
}

async function findRoutes() {
  await requestRoutes();
}

async function requestRoutes(options = {}) {
  const {
    keepNavigateScreen = false,
    originOverride = null,
    isReroute = false,
  } = options;
  errorMessage.value = "";
  const requestOrigin = originOverride || startLocation.value;
  if (!isConfirmedLocation(requestOrigin) || !isConfirmedLocation(endLocation.value)) {
    errorMessage.value = "Select and confirm both locations before finding routes.";
    return null;
  }
  if (isReroute && !canStartReroute(rerouteLoading.value)) {
    return null;
  }

  const startedAt = performance.now();
  if (isReroute) {
    rerouteLoading.value = true;
  } else {
    loading.value = true;
  }
  try {
    const body = await fetchRouteCandidates(requestOrigin);
    const responseReceivedAt = performance.now();

    result.value = preserveCurrentRouteResult(result.value, body);
    routeDepartureIso.value =
      body.request_settings?.departure_time || routeDepartureIso.value;
    lastMonitorAlertSignature = "";
    alternativePreparedForSignature = "";
    monitorAlert.value = null;
    dismissedPredictiveSignature.value = "";
    pendingAlternative.value = null;
    if (originOverride) {
      startLocation.value = requestOrigin;
    }
    selectedRouteId.value =
      body.recommended_route_id ||
      body.routes.find((route) => route.recommended)?.id ||
      body.routes.find((route) => route.roles.includes("Calmest"))?.id ||
      body.routes[0]?.id ||
      "";
    if (keepNavigateScreen) {
      positionMessage.value = "Route updated from your current location.";
    }
    await nextTick();
    if (isReroute) {
      const renderedAt = performance.now();
      rerouteTiming.value = {
        requestMilliseconds: Math.round(responseReceivedAt - startedAt),
        renderMilliseconds: Math.round(renderedAt - responseReceivedAt),
        totalMilliseconds: Math.round(renderedAt - startedAt),
      };
      if (import.meta.env.DEV) {
        console.debug("CitySense reroute timing", rerouteTiming.value);
      }
    }
    return body;
  } catch (error) {
    result.value = preserveCurrentRouteResult(result.value, null);
    errorMessage.value = messageForError(
      error,
      "We could not reach CitySense just now. Please try again shortly.",
    );
    if (isReroute) {
      rerouteMessage.value = "We could not find another route. Your current one still stands.";
    }
    return null;
  } finally {
    if (isReroute) {
      rerouteLoading.value = false;
    } else {
      loading.value = false;
    }
  }
}

async function fetchRouteCandidates(origin) {
  const response = await fetch(apiUrl("/api/routes"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(
      buildRouteRequest(
        origin,
        endLocation.value,
        crowdTolerance.value,
        selectRouteDeparture(departureTime.value, routeDepartureIso.value),
      ),
    ),
  });
  const body = await response.json();
  if (!response.ok) {
    throw new UserFacingError(body.error || "We could not find a route just now.");
  }
  return body;
}

function swapLocations() {
  const previousStart = startLocation.value;
  startLocation.value = endLocation.value;
  endLocation.value = previousStart;
  routeDepartureIso.value = "";
  result.value = null;
  selectedRouteId.value = "";
}

function navigateWithRoute(route) {
  selectedRouteId.value = route.id;
  changeScreen("navigate");
}

async function rerouteFromCurrentLocation(reason = "off-route") {
  if (!isConfirmedLocation(currentLocation.value)) {
    errorMessage.value = "Current Location is not available for rerouting.";
    return;
  }
  if (!canStartReroute(rerouteLoading.value)) {
    return;
  }

  const previousRoute = selectedRoute.value;
  const origin = {
    ...currentLocation.value,
    label: "Current Location",
    source: "reroute",
  };
  rerouteMessage.value = "";
  const body = await requestRoutes({
    keepNavigateScreen: true,
    originOverride: origin,
    isReroute: true,
  });
  if (!body) {
    return;
  }

  const nextRoute =
    body.routes.find((route) => route.id === body.recommended_route_id) ||
    body.routes.find((route) => route.recommended);
  rerouteMessage.value = compareObservedPeaks(previousRoute, nextRoute);
  if (reason === "overwhelming") {
    rerouteMessage.value = `Route checked for a lower-load option. ${rerouteMessage.value}`;
  }
}

/*
 * Overwhelm Mode has to work from a cold start.
 *
 * Someone who needs it has not necessarily planned a trip, and typing an
 * address is the one thing they cannot do in that moment. So the button asks
 * the device where it is, and treats a confirmed start as the fallback rather
 * than the requirement.
 */
async function resolveOverwhelmOrigin() {
  if (
    currentScreen.value === "navigate" &&
    isConfirmedLocation(currentLocation.value)
  ) {
    return currentLocation.value;
  }

  if (isLocationSupported()) {
    try {
      const position = await getCurrentPosition({
        enableHighAccuracy: false,
        timeout: 10000,
        maximumAge: 30000,
      });
      const located = locationFromPosition(position, "current_location");
      currentLocation.value = located;
      currentAccuracy.value = readPositionAccuracy(position);
      return located;
    } catch {
      // Permission refused or unavailable. A confirmed start still works.
    }
  }

  return isConfirmedLocation(startLocation.value) ? startLocation.value : null;
}

async function enterOverwhelmMode() {
  errorMessage.value = "";
  refugeLoading.value = true;
  try {
    const origin = await resolveOverwhelmOrigin();
    if (!origin) {
      errorMessage.value =
        "We could not work out where you are. Allow location access, or search for a start location and try again.";
      return;
    }
    const params = new URLSearchParams({
      lat: String(origin.lat),
      lon: String(origin.lon),
      label: origin.label,
      source: origin.source,
    });
    const response = await fetch(
      apiUrl("/api/refuges?" + params.toString()),
    );
    const body = await response.json();
    if (!response.ok || !body.nearest_refuge) {
      throw new UserFacingError(
        body.error || "We cannot find a quiet place right now.",
      );
    }

    refugeResponse.value = body;
    refuges.value = body.refuges;
    previousScreen.value = currentScreen.value;
    changeScreen("overwhelm");
  } catch (error) {
    errorMessage.value = messageForError(
      error,
      "We cannot find a quiet place right now. Look around you for somewhere to pause.",
    );
  } finally {
    refugeLoading.value = false;
  }
}

function exitOverwhelmMode() {
  changeScreen(previousScreen.value || "plan");
}

function returnToPlan() {
  changeScreen("plan");
}

function changeScreen(screen) {
  currentScreen.value = screen;
  if (screen === "navigate") {
    void startLocationTracking();
    startRouteMonitoring();
  } else {
    void stopLocationTracking();
    stopRouteMonitoring();
  }
  nextTick(() => {
    document.querySelector("[data-screen-heading]")?.focus();
  });
}

async function startLocationTracking() {
  locationTrackingRequested = true;
  if (
    geolocationWatchId !== null ||
    geolocationWatchStarting ||
    !isLocationSupported()
  ) {
    return;
  }

  geolocationWatchStarting = true;
  try {
    const watchId = await watchPosition(
      {
        enableHighAccuracy: false,
        timeout: 10000,
        maximumAge: 15000,
        minimumUpdateInterval: 5000,
      },
      (position) => {
        currentLocation.value = locationFromPosition(position, "current_location");
        currentAccuracy.value = readPositionAccuracy(position);
        positionMessage.value = "Current position updated. Route has not been recalculated.";
      },
      () => {
        positionMessage.value = "Current position updates are paused.";
      },
    );
    if (!locationTrackingRequested) {
      await clearWatch(watchId);
      return;
    }
    geolocationWatchId = watchId;
  } catch {
    positionMessage.value = "Current position updates are paused.";
  } finally {
    geolocationWatchStarting = false;
  }
}

async function stopLocationTracking() {
  locationTrackingRequested = false;
  const watchId = geolocationWatchId;
  geolocationWatchId = null;
  if (watchId !== null) {
    try {
      await clearWatch(watchId);
    } catch {
      // Navigation has already stopped. No location data is retained.
    }
  }
}

function startRouteMonitoring() {
  stopRouteMonitoring();
  navigationClock.value = Date.now();
  monitorActiveRoute();
  monitoringIntervalId = window.setInterval(() => {
    navigationClock.value = Date.now();
    void monitorActiveRoute();
  }, 60_000);
}

function stopRouteMonitoring() {
  if (monitoringIntervalId !== null) {
    window.clearInterval(monitoringIntervalId);
    monitoringIntervalId = null;
  }
  if (monitoringController) {
    monitoringController.abort();
    monitoringController = null;
  }
  monitoringInFlight = false;
  monitorAlert.value = null;
  pendingAlternative.value = null;
}

async function monitorActiveRoute() {
  if (
    currentScreen.value !== "navigate" ||
    monitoringInFlight ||
    !selectedRoute.value
  ) {
    return;
  }

  const coordinates = remainingRouteCoordinates(
    currentLocation.value,
    selectedRoute.value.geometry,
    500,
  );
  if (coordinates.length < 2) {
    return;
  }

  monitoringInFlight = true;
  monitoringController = new AbortController();
  try {
    const response = await fetch(apiUrl("/api/routes/monitor"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: monitoringController.signal,
      body: JSON.stringify({
        coordinates,
        crowd_tolerance: crowdTolerance.value,
      }),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new UserFacingError(
        body.error || "We cannot check crowds ahead right now.",
      );
    }

    if (!body.breached) {
      lastMonitorAlertSignature = "";
      alternativePreparedForSignature = "";
      return;
    }
    const signature = monitorAlertSignature(body);
    if (!shouldShowMonitorAlert(body, lastMonitorAlertSignature)) {
      if (
        isConfirmedLocation(currentLocation.value) &&
        alternativePreparedForSignature !== signature
      ) {
        alternativePreparedForSignature = signature;
        await prepareMonitoredAlternative();
      }
      return;
    }

    lastMonitorAlertSignature = signature;
    monitorAlert.value = body;
    if (!isConfirmedLocation(currentLocation.value)) {
      monitorAlert.value = {
        ...body,
        message: `${body.message} Current Location is needed to prepare an alternative.`,
      };
      return;
    }
    if (alternativePreparedForSignature !== signature) {
      alternativePreparedForSignature = signature;
      await prepareMonitoredAlternative();
    }
  } catch {
    // Active navigation continues unchanged when monitoring is unavailable.
  } finally {
    monitoringInFlight = false;
    monitoringController = null;
  }
}

async function prepareMonitoredAlternative() {
  if (alternativeLoading.value || !isConfirmedLocation(currentLocation.value)) {
    return;
  }
  alternativeLoading.value = true;
  try {
    const origin = {
      ...currentLocation.value,
      label: "Current Location",
      source: "reroute",
    };
    const body = await fetchRouteCandidates(origin);
    if (currentScreen.value === "navigate") {
      pendingAlternative.value = { body, origin };
    }
  } catch {
    pendingAlternative.value = null;
  } finally {
    alternativeLoading.value = false;
  }
}

function usePreparedAlternative() {
  if (!pendingAlternative.value) {
    return;
  }
  const { body, origin } = pendingAlternative.value;
  result.value = body;
  startLocation.value = origin;
  selectedRouteId.value =
    body.recommended_route_id ||
    body.routes.find((route) => route.recommended)?.id ||
    body.routes[0]?.id ||
    "";
  positionMessage.value = "Alternative route selected from your current position.";
  pendingAlternative.value = null;
  monitorAlert.value = null;
  lastMonitorAlertSignature = "";
  alternativePreparedForSignature = "";
  dismissedPredictiveSignature.value = "";
}

function dismissMonitorAlert() {
  monitorAlert.value = null;
  pendingAlternative.value = null;
}

function simulateAlongRoute() {
  const coordinates = selectedRoute.value?.geometry?.coordinates || [];
  if (!coordinates.length) {
    return;
  }
  simulatorIndex = Math.min(simulatorIndex + 1, coordinates.length - 1);
  setSimulatedPosition(coordinates[simulatorIndex], "Simulated movement along route.");
}

function simulateOffRoute() {
  const coordinates = selectedRoute.value?.geometry?.coordinates || [];
  if (!coordinates.length) {
    return;
  }
  const point = coordinates[Math.floor(coordinates.length / 2)];
  setSimulatedPosition(
    [point[0] + 0.002, point[1] + 0.002],
    "Simulated position is more than 120 metres off route.",
  );
}

function simulateArrival() {
  if (!result.value?.end) {
    return;
  }
  setSimulatedPosition(
    [result.value.end.lon, result.value.end.lat],
    "Simulated arrival at destination.",
  );
}

function setSimulatedPosition(coordinate, message) {
  currentLocation.value = {
    label: "Simulated Current Location",
    lon: coordinate[0],
    lat: coordinate[1],
    source: "current_location",
  };
  currentAccuracy.value = 8;
  positionMessage.value = message;
}

function locationFromPosition(position, source) {
  return {
    label: "Current Location",
    lat: position.coords.latitude,
    lon: position.coords.longitude,
    source,
  };
}

function readPositionAccuracy(position) {
  return Number.isFinite(position.coords.accuracy)
    ? position.coords.accuracy
    : null;
}
</script>

<template>
  <OverwhelmMode
    v-if="currentScreen === 'overwhelm'"
    :refuge="refugeResponse?.nearest_refuge"
    :calculation-basis="refugeResponse?.calculation_basis || ''"
    :status-message="refugeResponse?.data_status?.message"
    @exit="exitOverwhelmMode"
  />

  <div v-else class="app-shell">
    <header class="masthead">
      <a class="skip-link" href="#main">Skip to content</a>
      <button
        class="wordmark"
        type="button"
        aria-label="Return to CitySense Plan"
        @click="returnToPlan"
      >
        CitySense
      </button>
      <span class="tagline">Routes scored by their worst moment</span>
      <div class="masthead-controls">
        <button
          class="pill-toggle"
          type="button"
          :aria-label="theme === 'dark' ? 'Light mode' : 'Dark mode'"
          @click="toggleTheme"
        >
          {{ theme === "dark" ? "Light" : "Dark" }}
        </button>
        <button
          class="pill-toggle"
          :class="{ 'is-on': demoLocation }"
          type="button"
          :aria-pressed="demoLocation"
          aria-label="Demo Mode: report a fixed CBD position instead of reading this device"
          data-testid="demo-toggle"
          @click="toggleDemoLocation"
        >
          Demo
        </button>
      </div>
    </header>

    <p v-if="demoLocationNotice" class="demo-banner" role="status">
      {{ demoLocationNotice }}
    </p>

    <main id="main" class="main">
      <div v-if="currentScreen === 'plan'" class="screen">
        <h1 class="screen-title" data-screen-heading tabindex="-1">Where are you going?</h1>

        <form class="plan-form" @submit.prevent="findRoutes">
          <LocationSearch
            field-id="start"
            label="From"
            placeholder="Search a Melbourne address"
            :model-value="startLocation"
            :allow-current-location="true"
            :locating="locating"
            @update:model-value="setStartLocation"
            @use-current-location="useCurrentLocation"
          />

          <div class="swap-row">
            <button
              class="swap-button"
              type="button"
              aria-label="Swap start and destination"
              :disabled="loading"
              @click="swapLocations"
            >
              <span aria-hidden="true">⇅</span> Swap
            </button>
          </div>

          <LocationSearch
            field-id="destination"
            label="To"
            placeholder="Where to?"
            :model-value="endLocation"
            @update:model-value="setEndLocation"
          />

          <div class="field field-group">
            <label for="departure-time">Leaving</label>
            <input id="departure-time" v-model="departureTime" type="datetime-local" />
            <p class="field-hint">
              Optional. Tell us when you are leaving and we will show how busy it is likely to be.
            </p>
          </div>

          <button class="primary-button" type="submit" :disabled="!canFindRoutes">
            {{ loading ? "Finding routes..." : "Find Routes" }}
          </button>
        </form>

        <p v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</p>

        <section aria-live="polite" aria-labelledby="routes-title">
          <p class="screen-label">Route comparison</p>
          <h2 id="routes-title" class="section-title">Fastest and calmest</h2>
          <p v-if="result" class="field-hint">
            {{ result.start.label }} to {{ result.end.label }}
          </p>

          <div v-if="result" class="results">
            <RouteCard
              v-for="route in comparedRoutes"
              :key="route.id"
              :route="route"
              :role="formatRouteRoles(route.roles, 'Alternative')"
              :comparison-text="comparisonFor(route)"
              :selected="selectedRouteId === route.id"
              @select="navigateWithRoute"
            />
          </div>

          <p v-else class="notice">
            Type an address, then pick it from the list. We use the place you pick, not the words
            you type.
          </p>
        </section>

        <section
          v-if="departureSuggestion"
          class="panel"
          aria-labelledby="departure-suggestion-title"
          data-testid="departure-suggestion"
        >
          <p class="screen-label">Leaving later</p>
          <p id="departure-suggestion-title" class="panel-title">
            {{ departureSuggestion.message }}
          </p>
          <div class="panel-actions">
            <button
              class="secondary-button"
              type="button"
              :disabled="loading"
              @click="useSuggestedDeparture"
            >
              Leave at {{ suggestedDepartureLabel }} instead
            </button>
          </div>
        </section>

        <section class="tolerance" aria-labelledby="tolerance-title">
          <p class="tolerance-heading">
            <span id="tolerance-title">Crowd tolerance</span>
            <span class="tolerance-value">{{ crowdToleranceLabel }}</span>
          </p>
          <p class="tolerance-hint">
            How busy a street can get before we route you around it.
          </p>
          <div class="slider-wrap">
            <input
              id="crowd-tolerance"
              v-model.number="crowdToleranceValue"
              type="range"
              min="1"
              max="3"
              step="1"
              :aria-valuetext="crowdToleranceLabel"
              aria-labelledby="tolerance-title"
            />
            <div class="slider-labels" aria-hidden="true">
              <span>Low</span><span>Medium</span><span>High</span>
            </div>
          </div>
        </section>

        <RefugeFinder :confirmed-origin="startLocation" />
      </div>

      <div v-else class="screen screen-navigate">
        <header class="nav-head">
          <button class="back-link" type="button" @click="returnToPlan">
            &larr; Change plan
          </button>
          <div class="nav-summary">
            <h1 class="nav-route-name" data-screen-heading tabindex="-1">
              {{ result.start.label }} to {{ result.end.label }}
            </h1>
          </div>
          <p class="nav-route-where">
            Showing the {{ formatRouteRoles(selectedRoute?.roles).toLowerCase() }} route
          </p>
        </header>

        <div
          v-if="routeChoices.length"
          class="route-choice-bar"
          role="group"
          aria-label="Choose the route shown as selected"
        >
          <button
            v-for="choice in routeChoices"
            :key="choice.id"
            type="button"
            :aria-pressed="selectedRouteId === choice.id"
            :aria-label="`Show the ${choice.role.toLowerCase()} route, ${choice.minutes} minutes`"
            @click="selectedRouteId = choice.id"
          >
            <span class="choice-role">{{ choice.role }}</span>
            <span class="choice-minutes">{{ choice.minutes }} min</span>
          </button>
        </div>

        <section class="map-card" aria-label="Route map">
          <MapView
            :routes="result.routes"
            :start="result.start"
            :end="result.end"
            :selected-route-id="selectedRouteId"
            :sensors="result.sensors || []"
            :refuges="refuges"
            :current-location="currentLocation"
            :current-accuracy="currentAccuracy"
            :theme="theme"
          />
        </section>

        <ul class="legend" aria-label="Map legend">
          <li
            v-for="level in LOAD_LEVELS"
            :key="level"
            class="legend-item"
            :class="`band-${level.toLowerCase().replace('_', '-')}`"
          >
            <BandIcon :level="level" />
            {{ formatLoadLevel(level) }}
          </li>
          <li class="legend-item legend-neutral">
            <span class="refuge-pin" aria-hidden="true"></span>
            Quiet place
          </li>
          <li class="legend-item legend-neutral">
            <span class="here-pin" aria-hidden="true"></span>
            You are here
          </li>
          <li class="legend-item legend-neutral">
            <span class="route-line" aria-hidden="true"></span>
            Fastest
          </li>
          <li class="legend-item legend-neutral">
            <span class="route-line calmest-line" aria-hidden="true"></span>
            Calmest
          </li>
        </ul>

        <section class="panel" aria-live="polite">
          <template v-if="navigation?.arrived">
            <p class="screen-label">Arrived</p>
            <p class="panel-title">You have reached the destination area.</p>
            <p class="panel-body">Check your surroundings for the exact entrance.</p>
          </template>
          <template v-else>
            <p class="screen-label">Next step</p>
            <p class="panel-title">
              {{ navigation?.step?.instruction || "Continue along the selected route." }}
            </p>
            <p v-if="navigation?.step && navigation.distanceToNextStep !== null" class="panel-body">
              {{ navigation.distanceToNextStep }} m to this step
            </p>
            <p v-else-if="navigation?.step" class="panel-body">
              Distance updates when Current Location is available.
            </p>
            <p v-else class="panel-body">
              Step-by-step directions are not available for an example route.
            </p>
            <dl class="navigation-facts">
              <div>
                <dt>Remaining distance</dt>
                <dd>{{ navigation?.remainingDistance ?? selectedRoute?.distance_meters }} m</dd>
              </div>
              <div>
                <dt>Estimated time</dt>
                <dd>{{ navigation?.remainingMinutes ?? selectedRoute?.duration_minutes }} min</dd>
              </div>
            </dl>
          </template>
        </section>

        <section
          v-if="predictiveAlert"
          class="panel banner banner-warn"
          role="alert"
          data-testid="prediction-alert"
        >
          <span class="banner-icon" aria-hidden="true">◷</span>
          <p class="screen-label">Historical outlook</p>
          <p class="panel-title">{{ predictiveAlert.message }}</p>
          <p class="panel-body">
            {{ formatConfidence(predictiveAlert.confidence) }} · based on an imported
            historical baseline, not a live forecast.
          </p>
          <p v-if="!currentLocation" class="panel-body">
            Current Location is needed before CitySense can check another route.
          </p>
          <div class="panel-actions">
            <button
              class="secondary-button"
              type="button"
              :disabled="rerouteLoading || !currentLocation"
              @click="rerouteFromCurrentLocation('prediction')"
            >
              Check another route
            </button>
            <button type="button" class="text-button" @click="dismissPredictiveAlert">
              Keep current route
            </button>
          </div>
        </section>

        <section
          v-if="monitorAlert"
          class="panel banner"
          role="alert"
          data-testid="monitor-alert"
        >
          <p class="screen-label">Crowd change ahead</p>
          <p class="panel-title">{{ monitorAlert.message }}</p>
          <p class="panel-body">
            The current route remains active until you choose an alternative.
          </p>
          <div class="panel-actions">
            <button
              v-if="pendingAlternative"
              type="button"
              class="primary-button"
              @click="usePreparedAlternative"
            >
              Use prepared alternative
            </button>
            <p v-else-if="alternativeLoading" class="panel-body">Preparing an alternative...</p>
            <button type="button" class="text-button" @click="dismissMonitorAlert">
              Keep current route
            </button>
          </div>
        </section>

        <section v-if="currentLocation" class="panel" aria-labelledby="reroute-title">
          <p class="screen-label">Current position</p>
          <p id="reroute-title" class="panel-title">
            {{ offRoute ? "You may be off route." : "Position updates only." }}
          </p>
          <p class="panel-body">
            {{ positionMessage || "Your route will not change automatically." }}
          </p>
          <div class="panel-actions">
            <button
              class="secondary-button"
              type="button"
              :disabled="rerouteLoading"
              data-testid="manual-reroute"
              @click="rerouteFromCurrentLocation('off-route')"
            >
              {{ rerouteLoading ? "Rerouting..." : "Reroute from here" }}
            </button>
            <button
              class="secondary-button"
              type="button"
              :disabled="rerouteLoading"
              data-testid="overwhelming-reroute"
              @click="rerouteFromCurrentLocation('overwhelming')"
            >
              This route feels overwhelming
            </button>
          </div>
        </section>

        <p v-if="rerouteMessage" class="status-message" role="status">{{ rerouteMessage }}</p>
        <p v-if="showLocationSimulator && rerouteTiming" class="debug-status">
          Development timing: request {{ rerouteTiming.requestMilliseconds }} ms; render
          {{ rerouteTiming.renderMilliseconds }} ms; total
          {{ rerouteTiming.totalMilliseconds }} ms.
        </p>

        <section
          v-if="showLocationSimulator"
          class="panel panel-dashed"
          aria-label="Development location simulator"
        >
          <p class="screen-label">Development only</p>
          <p class="panel-title">Location simulator</p>
          <div class="simulator-actions">
            <button class="text-button" type="button" @click="simulateAlongRoute">
              Move along route
            </button>
            <button class="text-button" type="button" @click="simulateOffRoute">
              Move off route
            </button>
            <button class="text-button" type="button" @click="simulateArrival">Arrive</button>
          </div>
        </section>

        <p class="screen-label">Current route</p>
        <div class="results">
          <RouteCard
            v-if="selectedRoute"
            :route="selectedRoute"
            :role="formatRouteRoles(selectedRoute.roles)"
            :selected="true"
            :show-action="false"
          />
        </div>

        <DataStatus :route="selectedRoute" :data-status="result.data_status" />

        <p v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</p>
      </div>
    </main>

    <footer class="colophon">
      <p>
        Pedestrian counts, sensor locations and landmarks from the
        <a href="https://data.melbourne.vic.gov.au/">City of Melbourne Open Data Portal</a>, CC BY
        4.0. Street geometry &copy; OpenStreetMap contributors, basemap &copy; CARTO.
      </p>
      <p>
        CitySense is an early version. As you move, your route stays as planned until you ask for a
        new one. Streets without a sensor are shown as No Data, never as quiet.
      </p>
    </footer>

    <div class="overwhelm-bar">
      <button
        class="overwhelm-button"
        type="button"
        aria-label="Enter Overwhelm Mode"
        :disabled="refugeLoading"
        @click="enterOverwhelmMode"
      >
        {{ refugeLoading ? "Finding one quiet next step..." : "I'm overwhelmed" }}
      </button>
    </div>
  </div>
</template>
