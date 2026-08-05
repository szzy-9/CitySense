<script setup>
import { computed } from "vue";

import { formatDataStatus } from "../routeDisplay.js";


const props = defineProps({
  route: {
    type: Object,
    default: null,
  },
  dataStatus: {
    type: Object,
    default: null,
  },
});

const updatedText = computed(() => {
  const value = props.route?.last_updated || props.dataStatus?.updated_at;
  if (!value) {
    return "No live update time is available.";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "The latest update time could not be read.";
  }

  const formatted = new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Australia/Melbourne",
  }).format(date);
  return `Latest pedestrian data updated at ${formatted}.`;
});

const coverageText = computed(() => {
  if (!props.route) {
    return "";
  }
  if (props.route.sensory_level === "NO_DATA") {
    return "No reliable crowd data for this route.";
  }
  if (props.route.coverage < 1) {
    return "Sensor coverage is limited for part of this route.";
  }
  return "All displayed route segments have nearby sensor data.";
});
</script>

<template>
  <section v-if="route && dataStatus" class="data-status-card" aria-labelledby="data-status-title">
    <div class="status-title-row">
      <h2 id="data-status-title">Data status</h2>
      <span class="status-chip" :class="`status-${route.data_status.toLowerCase()}`">
        {{ formatDataStatus(route.data_status) }}
      </span>
    </div>
    <p>{{ updatedText }}</p>
    <p v-if="dataStatus.pedestrian_source === 'fallback'">
      Using local sample pedestrian data. It has no live timestamp.
    </p>
    <p v-if="dataStatus.route_source === 'fallback'">
      Route geometry is a clearly marked prototype because the route service is unavailable.
    </p>
    <p>{{ coverageText }}</p>
    <p>
      Sensor locations: {{ dataStatus.sensor_location_source || "No data" }}.
      Historical profiles: {{ dataStatus.historical_profile_source || "No data" }}.
      Refuges: {{ dataStatus.refuge_source || "No data" }}.
    </p>
    <p class="data-source-line">
      {{ route.matched_sensor_count }} nearby sensor{{
        route.matched_sensor_count === 1 ? "" : "s"
      }} used for this route.
    </p>
  </section>
</template>
