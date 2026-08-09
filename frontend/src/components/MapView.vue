<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import L from "leaflet";

import { formatLoadLevel, nextFollowMode } from "../routeDisplay.js";


/*
 * Leaflet directly, rather than a wrapper component.
 *
 * The map draws one polyline per scored segment so each stretch can carry its
 * own band, and unmeasured stretches need a dashed casing rather than a
 * colour: a street we cannot measure must never look like a street we measured
 * and found quiet.
 */

const TILES = {
  dark: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
  light: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
};

const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, ' +
  '&copy; <a href="https://carto.com/attributions">CARTO</a>';

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
  theme: {
    type: String,
    default: "dark",
  },
});

const emit = defineEmits(["follow-change"]);

const mapElement = ref(null);
const following = ref(true);
let map = null;
let tileLayer = null;
let routeGroup = null;
let positionGroup = null;
let programmaticMove = false;

onMounted(() => {
  map = L.map(mapElement.value, {
    zoomControl: true,
    scrollWheelZoom: false,
  }).setView([-37.8136, 144.9631], 14);

  tileLayer = L.tileLayer(TILES[props.theme] || TILES.dark, {
    maxZoom: 19,
    attribution: TILE_ATTRIBUTION,
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

// The basemap and the interface share one brightness. A dark UI over bright
// tiles is the single loudest thing this app could put on screen.
watch(
  () => props.theme,
  (theme) => {
    if (tileLayer) {
      tileLayer.setUrl(TILES[theme] || TILES.dark);
    }
    drawMapContent();
    updateCurrentLocationMarker();
  },
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

  L.polyline(routeCoordinates, {
    color: readColor("--ground", "#12171c"),
    weight: selected ? 12 : 8,
    opacity: selected ? 0.9 : 0.5,
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
    const noData = segment.sensory_level === "NO_DATA";
    const line = L.polyline(points, {
      color: levelColor(segment.sensory_level),
      weight: selected ? 7 : 4,
      opacity: selected ? 1 : 0.5,
      lineCap: "round",
      // Dashes mean either "no sensor here" or "this is the calmer of the two
      // routes". Both are read against the legend, never on their own.
      dashArray: noData ? "6 6" : isCalmestOnly ? "12 8" : null,
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
    color: readColor("--ground", "#12171c"),
    weight: 2,
    fillColor: levelColor(sensor.sensory_level),
    fillOpacity: 1,
  })
    .bindTooltip(
      createTextElement(
        `Pedestrian sensor: ${sensor.name}. ${formatLoadLevel(sensor.sensory_level)} load.`,
      ),
    )
    .addTo(routeGroup);
}

function addRefugeMarker(refuge) {
  L.marker([refuge.latitude, refuge.longitude], {
    icon: L.divIcon({
      className: "refuge-pin-wrap",
      html: '<span class="refuge-pin"></span>',
      iconSize: [18, 18],
      iconAnchor: [9, 9],
    }),
    keyboard: true,
    alt: `Quiet place: ${refuge.name}`,
  })
    .bindTooltip(createTextElement(`Quiet place: ${refuge.name}`))
    .addTo(routeGroup);
}

function addPlaceMarker(place, label, isStart, bounds) {
  if (!place) {
    return;
  }

  const point = [place.lat, place.lon];
  L.circleMarker(point, {
    radius: 8,
    color: readColor("--ground", "#12171c"),
    weight: 3,
    fillColor: isStart
      ? readColor("--ink", "#e8edf2")
      : readColor("--band-high", "#e4573d"),
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

  const here = readColor("--here", "#9db4d8");
  if (Number.isFinite(props.currentAccuracy) && props.currentAccuracy > 0) {
    L.circle([props.currentLocation.lat, props.currentLocation.lon], {
      radius: props.currentAccuracy,
      color: here,
      weight: 1,
      fillColor: here,
      fillOpacity: 0.12,
      interactive: false,
    }).addTo(positionGroup);
  }

  L.circleMarker([props.currentLocation.lat, props.currentLocation.lon], {
    radius: 8,
    color: readColor("--ink", "#e8edf2"),
    weight: 3,
    fillColor: here,
    fillOpacity: 1,
  })
    .bindTooltip(createTextElement("Current Location"), { direction: "top" })
    .addTo(positionGroup);

  if (following.value) {
    followCurrentLocation();
  }
}

function pauseFollowingForMapInteraction() {
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
    LOW: ["--band-low", "#4fb3a6"],
    MODERATE: ["--band-moderate", "#e8a33d"],
    HIGH: ["--band-high", "#e4573d"],
    NO_DATA: ["--band-nodata", "#7a8896"],
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
      aria-label="Map showing how busy the route is, your position, pedestrian sensors, and quiet places"
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
