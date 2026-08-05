<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";

import DataStatus from "./components/DataStatus.vue";
import LocationSearch from "./components/LocationSearch.vue";
import MapView from "./components/MapView.vue";
import OverwhelmMode from "./components/OverwhelmMode.vue";
import RefugeFinder from "./components/RefugeFinder.vue";
import RouteCard from "./components/RouteCard.vue";
import {
  buildRouteRequest,
  buildCalmestComparison,
  canStartReroute,
  compareObservedPeaks,
  formatLoadLevel,
  isConfirmedLocation,
  isOffRoute,
  monitorAlertSignature,
  navigationSummary,
  preserveCurrentRouteResult,
  remainingRouteCoordinates,
  shouldShowMonitorAlert,
  selectRouteDeparture,
} from "./routeDisplay.js";


const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? "http://localhost:5000" : "");

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
const pendingAlternative = ref(null);
const alternativeLoading = ref(false);
const showLocationSimulator = import.meta.env.DEV;
const arrivalDistanceMetres = Number(
  import.meta.env.VITE_ARRIVAL_DISTANCE_METERS || 35,
);
let geolocationWatchId = null;
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

const calmestComparison = computed(() => {
  return buildCalmestComparison(fastestRoute.value, calmestRoute.value);
});

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

const canFindRoutes = computed(() => {
  return (
    isConfirmedLocation(startLocation.value) &&
    isConfirmedLocation(endLocation.value) &&
    !loading.value
  );
});

onMounted(async () => {
  await loadRefuges();
});

onBeforeUnmount(() => {
  stopLocationTracking();
  stopRouteMonitoring();
});

async function loadRefuges() {
  try {
    const response = await fetch(API_BASE_URL + "/api/refuges");
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

function useCurrentLocation() {
  errorMessage.value = "";
  if (!navigator.geolocation) {
    errorMessage.value = "Current Location is not supported by this browser.";
    return;
  }

  locating.value = true;
  navigator.geolocation.getCurrentPosition(
    (position) => {
      const location = locationFromPosition(position, "current_location");
      currentLocation.value = location;
      currentAccuracy.value = readPositionAccuracy(position);
      setStartLocation(location);
      locating.value = false;
    },
    () => {
      errorMessage.value = "Current Location was not available. Search for an address instead.";
      locating.value = false;
    },
    {
      enableHighAccuracy: false,
      timeout: 10000,
      maximumAge: 30000,
    },
  );
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
    errorMessage.value = error.message || "Something went wrong. Please try again.";
    if (isReroute) {
      rerouteMessage.value = "Reroute failed. Your current route is still shown.";
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
  const response = await fetch(API_BASE_URL + "/api/routes", {
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
    throw new Error(body.error || "Could not find routes.");
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

async function enterOverwhelmMode() {
  errorMessage.value = "";
  const origin =
    currentScreen.value === "navigate" && isConfirmedLocation(currentLocation.value)
      ? currentLocation.value
      : startLocation.value;
  if (!isConfirmedLocation(origin)) {
    errorMessage.value = "Confirm a start location before opening Overwhelm Mode.";
    return;
  }

  refugeLoading.value = true;
  try {
    const params = new URLSearchParams({
      lat: String(origin.lat),
      lon: String(origin.lon),
      label: origin.label,
      source: origin.source,
    });
    const response = await fetch(
      API_BASE_URL + "/api/refuges?" + params.toString(),
    );
    const body = await response.json();
    if (!response.ok || !body.nearest_refuge) {
      throw new Error(body.error || "Refuge information is unavailable.");
    }

    refugeResponse.value = body;
    refuges.value = body.refuges;
    previousScreen.value = currentScreen.value;
    changeScreen("overwhelm");
  } catch (error) {
    errorMessage.value = error.message || "Refuge information is unavailable.";
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
    startLocationTracking();
    startRouteMonitoring();
  } else {
    stopLocationTracking();
    stopRouteMonitoring();
  }
  nextTick(() => {
    document.querySelector("[data-screen-heading]")?.focus();
  });
}

function startLocationTracking() {
  if (
    geolocationWatchId !== null ||
    !navigator.geolocation
  ) {
    return;
  }

  geolocationWatchId = navigator.geolocation.watchPosition(
    (position) => {
      currentLocation.value = locationFromPosition(position, "current_location");
      currentAccuracy.value = readPositionAccuracy(position);
      positionMessage.value = "Current position updated. Route has not been recalculated.";
    },
    () => {
      positionMessage.value = "Current position updates are paused.";
    },
    {
      enableHighAccuracy: false,
      timeout: 10000,
      maximumAge: 15000,
    },
  );
}

function stopLocationTracking() {
  if (geolocationWatchId !== null && navigator.geolocation) {
    navigator.geolocation.clearWatch(geolocationWatchId);
    geolocationWatchId = null;
  }
}

function startRouteMonitoring() {
  stopRouteMonitoring();
  monitorActiveRoute();
  monitoringIntervalId = window.setInterval(monitorActiveRoute, 60_000);
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
    const response = await fetch(API_BASE_URL + "/api/routes/monitor", {
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
      throw new Error(body.error || "Route monitoring is unavailable.");
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
    <header class="site-header">
      <button class="brand-button" type="button" aria-label="Return to CitySense Plan" @click="returnToPlan">
        <span class="brand-mark" aria-hidden="true">C</span>
        <span>CitySense</span>
      </button>
      <p>Melbourne on foot, at your pace.</p>
    </header>

    <main v-if="currentScreen === 'plan'" class="screen plan-screen">
      <section class="screen-intro" aria-labelledby="plan-title">
        <p class="screen-label">Plan</p>
        <h1 id="plan-title" data-screen-heading tabindex="-1">Choose a route with less guesswork.</h1>
        <p>Search, select, and confirm both locations before comparing routes.</p>
      </section>

      <form class="journey-form surface-card" @submit.prevent="findRoutes">
        <div class="place-fields">
          <LocationSearch
            field-id="start"
            label="Start"
            :model-value="startLocation"
            :api-base-url="API_BASE_URL"
            :allow-current-location="true"
            :locating="locating"
            @update:model-value="setStartLocation"
            @use-current-location="useCurrentLocation"
          />

          <button
            class="swap-button"
            type="button"
            aria-label="Swap start and destination"
            :disabled="loading"
            @click="swapLocations"
          >
            Swap
          </button>

          <LocationSearch
            field-id="destination"
            label="Destination"
            :model-value="endLocation"
            :api-base-url="API_BASE_URL"
            @update:model-value="setEndLocation"
          />
        </div>

        <div class="departure-row">
          <div class="field-group">
            <label for="departure-time">Departure time</label>
            <input id="departure-time" v-model="departureTime" type="datetime-local" />
          </div>
          <p>
            Optional. Historical outlook is shown only when imported baseline data is available.
          </p>
        </div>

        <button class="primary-button" type="submit" :disabled="!canFindRoutes">
          {{ loading ? "Finding routes..." : "Find Routes" }}
        </button>
      </form>

      <p v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</p>

      <section class="route-results" aria-live="polite" aria-labelledby="routes-title">
        <div class="section-heading">
          <p class="screen-label">Route comparison</p>
          <h2 id="routes-title">Fastest and calmest</h2>
          <p v-if="result">{{ result.start.label }} to {{ result.end.label }}</p>
        </div>

        <div v-if="result" class="route-grid">
          <RouteCard
            v-if="fastestRoute"
            :route="fastestRoute"
            role="Fastest"
            :selected="selectedRouteId === fastestRoute.id"
            @select="navigateWithRoute"
          />
          <RouteCard
            v-if="calmestRoute"
            :route="calmestRoute"
            role="Calmest"
            :comparison-text="calmestComparison"
            :selected="selectedRouteId === calmestRoute.id"
            @select="navigateWithRoute"
          />
        </div>

        <div v-else class="empty-state surface-card">
          <p>Type an address, then select a result to confirm it.</p>
          <p>Typed text alone is not used as a route location.</p>
        </div>
      </section>

      <section class="tolerance-card surface-card" aria-labelledby="tolerance-title">
        <div>
          <p class="screen-label">Route preference</p>
          <h2 id="tolerance-title">Crowd tolerance: {{ crowdToleranceLabel }}</h2>
          <p>This sets the maximum observed load used for the default recommendation.</p>
        </div>
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

      <RefugeFinder
        :api-base-url="API_BASE_URL"
        :confirmed-origin="startLocation"
      />

      <button
        class="overwhelm-button"
        type="button"
        aria-label="Enter Overwhelm Mode"
        :disabled="refugeLoading || !isConfirmedLocation(startLocation)"
        @click="enterOverwhelmMode"
      >
        {{ refugeLoading ? "Finding one quiet next step..." : "I'm Overwhelmed" }}
      </button>
    </main>

    <main v-else class="screen navigate-screen">
      <section class="navigate-status" aria-labelledby="navigate-title">
        <div>
          <p class="screen-label">Navigate</p>
          <h1 id="navigate-title" data-screen-heading tabindex="-1">
            {{ result.start.label }} to {{ result.end.label }}
          </h1>
          <p>Selected: {{ selectedRoute?.roles.join(" and ") || "Route" }}</p>
        </div>
        <button class="secondary-button" type="button" @click="returnToPlan">Back to Plan</button>
      </section>

      <div class="route-choice-bar" aria-label="Choose the route shown as selected">
        <button
          v-if="fastestRoute"
          type="button"
          :aria-pressed="selectedRouteId === fastestRoute.id"
          @click="selectedRouteId = fastestRoute.id"
        >
          Fastest - {{ fastestRoute.duration_minutes }} min
        </button>
        <button
          v-if="calmestRoute"
          type="button"
          :aria-pressed="selectedRouteId === calmestRoute.id"
          @click="selectedRouteId = calmestRoute.id"
        >
          Calmest - {{ formatLoadLevel(calmestRoute.sensory_level) }}
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
        />
      </section>

      <section class="navigation-guidance surface-card" aria-live="polite">
        <template v-if="navigation?.arrived">
          <p class="screen-label">Arrived</p>
          <h2>You have reached the destination area.</h2>
          <p>Check your surroundings for the exact entrance.</p>
        </template>
        <template v-else>
          <p class="screen-label">Next step</p>
          <h2>{{ navigation?.step?.instruction || "Continue along the selected route." }}</h2>
          <p v-if="navigation?.step && navigation.distanceToNextStep !== null">
            {{ navigation.distanceToNextStep }} m to this step
          </p>
          <p v-else-if="navigation?.step">
            Distance updates when Current Location is available.
          </p>
          <p v-else>Turn-by-turn steps are unavailable for this prototype route.</p>
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

      <section v-if="currentLocation" class="reroute-card surface-card" aria-labelledby="reroute-title">
        <div>
          <p class="screen-label">Current position</p>
          <h2 id="reroute-title">{{ offRoute ? "You may be off route." : "Position updates only." }}</h2>
          <p>{{ positionMessage || "Your route will not change automatically." }}</p>
        </div>
        <div class="reroute-actions">
          <button
            class="secondary-button"
            type="button"
            :disabled="rerouteLoading"
            data-testid="manual-reroute"
            @click="rerouteFromCurrentLocation('off-route')"
          >
            {{ rerouteLoading ? "Rerouting..." : "Reroute from Current Location" }}
          </button>
          <button
            class="overwhelming-route-button"
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
        Development timing: request {{ rerouteTiming.requestMilliseconds }} ms;
        render {{ rerouteTiming.renderMilliseconds }} ms;
        total {{ rerouteTiming.totalMilliseconds }} ms.
      </p>

      <section
        v-if="selectedRoute?.prediction_alert"
        class="prediction-alert"
        role="alert"
        data-testid="prediction-alert"
      >
        <span class="prediction-alert-icon" aria-hidden="true">◷</span>
        <div>
          <p class="screen-label">Historical outlook</p>
          <h2>{{ selectedRoute.prediction_alert.message }}</h2>
          <p>
            {{ selectedRoute.prediction_alert.confidence }} confidence · based on an
            imported historical baseline, not a live forecast.
          </p>
          <p v-if="!currentLocation">
            Current Location is needed before CitySense can check another route.
          </p>
        </div>
        <button
          class="secondary-button"
          type="button"
          :disabled="rerouteLoading || !currentLocation"
          @click="rerouteFromCurrentLocation('prediction')"
        >
          Check another route
        </button>
      </section>

      <section v-if="monitorAlert" class="monitor-alert" role="alert" data-testid="monitor-alert">
        <div>
          <p class="screen-label">Crowd change ahead</p>
          <h2>{{ monitorAlert.message }}</h2>
          <p>The current route remains active until you choose an alternative.</p>
        </div>
        <div class="monitor-actions">
          <button
            v-if="pendingAlternative"
            type="button"
            class="primary-button"
            @click="usePreparedAlternative"
          >
            Use prepared alternative
          </button>
          <p v-else-if="alternativeLoading">Preparing an alternative...</p>
          <button type="button" class="text-button" @click="dismissMonitorAlert">
            Keep current route
          </button>
        </div>
      </section>

      <section v-if="showLocationSimulator" class="simulator-card surface-card" aria-label="Development location simulator">
        <p class="screen-label">Development only</p>
        <h2>Location simulator</h2>
        <div class="simulator-actions">
          <button type="button" @click="simulateAlongRoute">Move along route</button>
          <button type="button" @click="simulateOffRoute">Move off route</button>
          <button type="button" @click="simulateArrival">Arrive</button>
        </div>
      </section>

      <section class="map-legend" aria-labelledby="legend-title">
        <h2 id="legend-title">Map legend</h2>
        <ul>
          <li><span class="legend-swatch load-low">Low</span><span>Low load</span></li>
          <li><span class="legend-swatch load-moderate">Moderate</span><span>Moderate</span></li>
          <li><span class="legend-swatch load-high">High</span><span>High</span></li>
          <li><span class="legend-swatch load-no-data">No Data</span><span>No Data</span></li>
          <li><span class="legend-dot refuge-dot" aria-hidden="true"></span><span>Refuge</span></li>
          <li><span class="legend-dot current-dot" aria-hidden="true"></span><span>Current Location</span></li>
          <li><span class="route-line fastest-line" aria-hidden="true"></span><span>Fastest</span></li>
          <li><span class="route-line calmest-line" aria-hidden="true"></span><span>Calmest</span></li>
        </ul>
      </section>

      <section class="navigate-details">
        <div>
          <div class="section-heading">
            <p class="screen-label">Current route</p>
            <h2>Route summary</h2>
          </div>
          <RouteCard
            v-if="selectedRoute"
            :route="selectedRoute"
            :role="selectedRoute.roles.join(' and ') || 'Selected'"
            :selected="true"
            :show-action="false"
          />
        </div>
        <DataStatus :route="selectedRoute" :data-status="result.data_status" />
      </section>

      <p v-if="errorMessage" class="error-message" role="alert">{{ errorMessage }}</p>
      <button
        class="overwhelm-button"
        type="button"
        aria-label="Enter Overwhelm Mode"
        :disabled="refugeLoading"
        @click="enterOverwhelmMode"
      >
        {{ refugeLoading ? "Finding one quiet next step..." : "I'm Overwhelmed" }}
      </button>
    </main>

    <footer>
      <p>CitySense prototype. Position updates do not automatically recalculate routes.</p>
    </footer>
  </div>
</template>
