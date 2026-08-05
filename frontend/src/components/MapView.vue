<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import L from "leaflet";

import { formatLoadLevel, nextFollowMode } from "../routeDisplay.js";


const props = defineProps({
  routes: {
    type: Array,
    default: () => [],
  },
  start: {
    type: Object,
    default: null,
  },
  end: {
    type: Object,
    default: null,
  },
  selectedRouteId: {
    type: String,
    default: "",
  },
  sensors: {
    type: Array,
    default: () => [],
  },
  refuges: {
    type: Array,
    default: () => [],
  },
  currentLocation: {
    type: Object,
    default: null,
  },
  currentAccuracy: {
    type: Number,
    default: null,
  },
});

const emit = defineEmits(["follow-change"]);

const mapElement = ref(null);
const following = ref(true);
let map = null;
let routeGroup = null;
let positionGroup = null;
let programmaticMove = false;

onMounted(() => {
  map = L.map(mapElement.value, {
    zoomControl: true,
    scrollWheelZoom: false,
  }).setView([-37.8136, 144.9631], 14);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);

  routeGroup = L.layerGroup().addTo(map);
  positionGroup = L.layerGroup().addTo(map);
  map.on("dragstart zoomstart", pauseFollowingForMapInteraction);
  drawMapContent();
  updateCurrentLocationMarker();
  map.invalidateSize();
});

onBeforeUnmount(() => {
  if (map) {
    map.remove();
    map = null;
  }
});

watch(
  () => [
    props.routes,
    props.start,
    props.end,
    props.selectedRouteId,
    props.sensors,
    props.refuges,
  ],
  () => drawMapContent(),
  { deep: true },
);

watch(
  () => [props.currentLocation, props.currentAccuracy],
  () => updateCurrentLocationMarker(),
  { deep: true },
);

function drawMapContent() {
  if (!map || !routeGroup) {
    return;
  }

  routeGroup.clearLayers();
  const bounds = [];
  const routes = [...props.routes].sort((route) => {
    return route.id === props.selectedRouteId ? 1 : -1;
  });

  routes.forEach((route) => drawRoute(route, bounds));
  props.sensors.forEach(addSensorMarker);
  props.refuges.forEach(addRefugeMarker);
  addPlaceMarker(props.start, "Start", true, bounds);
  addPlaceMarker(props.end, "Destination", false, bounds);

  if (bounds.length) {
    moveMapProgrammatically(() => {
      map.fitBounds(bounds, { padding: [38, 38], maxZoom: 16, animate: false });
    });
  }
}

function drawRoute(route, bounds) {
  const selected = route.id === props.selectedRouteId;
  const routeCoordinates = route.geometry.coordinates.map(toLatLon);
  const isCalmestOnly =
    route.roles.includes("Calmest") && !route.roles.includes("Fastest");
  const dashArray = isCalmestOnly ? "10 8" : null;

  L.polyline(routeCoordinates, {
    color: readColor("--color-surface", "#ffffff"),
    weight: selected ? 11 : 7,
    opacity: selected ? 0.95 : 0.55,
  }).addTo(routeGroup);

  const segments = route.segments?.length
    ? route.segments
    : [
        {
          geometry: route.geometry,
          sensory_level: route.sensory_level,
        },
      ];

  segments.forEach((segment) => {
    const points = segment.geometry.coordinates.map(toLatLon);
    const line = L.polyline(points, {
      color: levelColor(segment.sensory_level),
      weight: selected ? 7 : 4,
      opacity: selected ? 0.95 : 0.5,
      dashArray,
    });
    const roles = route.roles.length ? route.roles.join(" and ") : "Alternative";
    line.bindTooltip(
      createTextElement(
        `${roles}: ${formatLoadLevel(segment.sensory_level)} load`,
      ),
      { sticky: true },
    );
    line.addTo(routeGroup);
    bounds.push(...points);
  });
}

function addSensorMarker(sensor) {
  L.circleMarker([sensor.lat, sensor.lon], {
    radius: 5,
    color: readColor("--color-dark", "#123f3b"),
    weight: 2,
    fillColor: levelColor(sensor.sensory_level),
    fillOpacity: 0.9,
  })
    .bindTooltip(
      createTextElement(
        `Pedestrian sensor: ${sensor.name}. ${formatLoadLevel(sensor.sensory_level)} load.`,
      ),
    )
    .addTo(routeGroup);
}

function addRefugeMarker(refuge) {
  L.circleMarker([refuge.latitude, refuge.longitude], {
    radius: 7,
    color: readColor("--color-dark", "#123f3b"),
    weight: 2,
    fillColor: readColor("--color-refuge", "#dce8ff"),
    fillOpacity: 1,
  })
    .bindTooltip(createTextElement(`Prototype refuge: ${refuge.name}`))
    .addTo(routeGroup);
}

function addPlaceMarker(place, label, isStart, bounds) {
  if (!place) {
    return;
  }

  const point = [place.lat, place.lon];
  L.circleMarker(point, {
    radius: 9,
    color: readColor("--color-surface", "#ffffff"),
    weight: 3,
    fillColor: isStart
      ? readColor("--color-dark", "#123f3b")
      : readColor("--color-high", "#8f3d43"),
    fillOpacity: 1,
  })
    .bindTooltip(createTextElement(`${label}: ${place.label}`), { direction: "top" })
    .addTo(routeGroup);

  bounds.push(point);
}

function updateCurrentLocationMarker() {
  if (!positionGroup) {
    return;
  }

  positionGroup.clearLayers();
  if (!props.currentLocation) {
    return;
  }

  if (Number.isFinite(props.currentAccuracy) && props.currentAccuracy > 0) {
    L.circle([props.currentLocation.lat, props.currentLocation.lon], {
      radius: props.currentAccuracy,
      color: readColor("--color-current", "#315b8a"),
      weight: 1,
      fillColor: readColor("--color-current", "#315b8a"),
      fillOpacity: 0.12,
      interactive: false,
    }).addTo(positionGroup);
  }

  L.circleMarker([props.currentLocation.lat, props.currentLocation.lon], {
    radius: 9,
    color: readColor("--color-surface", "#ffffff"),
    weight: 3,
    fillColor: readColor("--color-current", "#315b8a"),
    fillOpacity: 1,
  })
    .bindTooltip(createTextElement("Current Location"), { direction: "top" })
    .addTo(positionGroup);

  if (following.value) {
    followCurrentLocation();
  }
}

function pauseFollowingForMapInteraction(event) {
  if (!programmaticMove && following.value) {
    following.value = nextFollowMode(following.value, "manual-map-move");
    emit("follow-change", following.value);
  }
}

function recentre() {
  following.value = nextFollowMode(following.value, "recentre");
  emit("follow-change", following.value);
  followCurrentLocation();
}

function followCurrentLocation() {
  if (!map || !props.currentLocation) {
    return;
  }
  moveMapProgrammatically(() => {
    map.setView(
      [props.currentLocation.lat, props.currentLocation.lon],
      Math.max(map.getZoom(), 16),
      { animate: false },
    );
  });
}

function moveMapProgrammatically(action) {
  programmaticMove = true;
  action();
  window.setTimeout(() => {
    programmaticMove = false;
  }, 0);
}

function levelColor(level) {
  const properties = {
    LOW: ["--color-low", "#b9dec9"],
    MODERATE: ["--color-moderate", "#e3bd71"],
    HIGH: ["--color-high", "#8f3d43"],
    NO_DATA: ["--color-no-data", "#899599"],
  };
  const [property, fallback] = properties[level] || properties.NO_DATA;
  return readColor(property, fallback);
}

function readColor(property, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(property);
  return value.trim() || fallback;
}

function toLatLon(point) {
  return [point[1], point[0]];
}

function createTextElement(text) {
  const element = document.createElement("span");
  element.textContent = text;
  return element;
}
</script>

<template>
  <div class="map-wrap">
    <div
      ref="mapElement"
      class="map"
      role="region"
      aria-label="Map showing route load, current position, pedestrian sensors, and prototype refuges"
    ></div>
    <button
      v-if="currentLocation && !following"
      class="recentre-button"
      type="button"
      data-testid="recentre-button"
      @click="recentre"
    >
      Re-centre
    </button>
    <p class="follow-status" aria-live="polite">
      {{ following ? "Follow Mode on" : "Follow Mode paused" }}
    </p>
  </div>
</template>
