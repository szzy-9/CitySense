<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import L from "leaflet";


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
});

const mapElement = ref(null);
let map = null;
let routeGroup = null;

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
  drawRoutes();
});

onBeforeUnmount(() => {
  if (map) {
    map.remove();
  }
});

watch(
  () => [props.routes, props.start, props.end],
  () => drawRoutes(),
  { deep: true },
);

function drawRoutes() {
  if (!map || !routeGroup) {
    return;
  }

  routeGroup.clearLayers();
  const bounds = [];

  props.routes.forEach((route) => {
    const latLonPoints = route.geometry.coordinates.map((point) => [point[1], point[0]]);
    const color = route.roles.includes("Calmest") ? "#6d55c7" : "#087f73";

    L.polyline(latLonPoints, {
      color: "#ffffff",
      weight: 9,
      opacity: 0.9,
    }).addTo(routeGroup);

    L.polyline(latLonPoints, {
      color,
      weight: 5,
      opacity: 0.95,
      dashArray: route.roles.includes("Calmest") ? "10 8" : null,
    })
      .bindPopup(
        "<strong>" + (route.roles.join(" + ") || "Alternative") + "</strong><br>" +
          route.duration_minutes + " min · " + route.crowd_label,
      )
      .addTo(routeGroup);

    bounds.push(...latLonPoints);
  });

  addPlaceMarker(props.start, "Start", "start", bounds);
  addPlaceMarker(props.end, "Destination", "end", bounds);

  if (bounds.length) {
    map.fitBounds(bounds, { padding: [45, 45], maxZoom: 16 });
  }
}

function addPlaceMarker(place, label, className, bounds) {
  if (!place) {
    return;
  }

  const point = [place.lat, place.lon];
  L.circleMarker(point, {
    radius: 9,
    color: "#ffffff",
    weight: 3,
    fillColor: className === "start" ? "#087f73" : "#f06449",
    fillOpacity: 1,
  })
    .bindTooltip(label + ": " + place.name, { direction: "top" })
    .addTo(routeGroup);

  bounds.push(point);
}
</script>

<template>
  <div
    ref="mapElement"
    class="map"
    role="region"
    aria-label="Map showing the selected Melbourne walking routes"
  ></div>
</template>

