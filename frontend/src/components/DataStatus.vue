<script setup>
import { computed } from "vue";

import { formatDataStatus, formatSourceLabel } from "../routeDisplay.js";


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
    return "We do not have a live update time for this data.";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "We could not read the time of the latest update.";
  }

  const formatted = new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Australia/Melbourne",
  }).format(date);
  return `Crowd counts last updated ${formatted}.`;
});

const coverageText = computed(() => {
  if (!props.route) {
    return "";
  }
  if (props.route.sensory_level === "NO_DATA") {
    return "No sensors are reporting along this route right now.";
  }
  if (props.route.coverage < 1) {
    return "Part of this route has no sensors nearby, so it is not checked.";
  }
  return "Every part of this route has a sensor nearby.";
});
</script>

<template>
  <section v-if="route && dataStatus" class="data-status-card" aria-labelledby="data-status-title">
    <div class="status-title-row">
      <h2 id="data-status-title">Where this comes from</h2>
      <span class="status-chip" :class="`status-${route.data_status.toLowerCase()}`">
        {{ formatDataStatus(route.data_status) }}
      </span>
    </div>
    <p>{{ updatedText }}</p>
    <p v-if="dataStatus.pedestrian_source === 'fallback'">
      These are sample crowd counts, not today's. Treat them as a preview.
    </p>
    <p v-if="dataStatus.route_source === 'fallback'">
      Live routing is unavailable, so these are example routes rather than real ones.
    </p>
    <p>{{ coverageText }}</p>
    <p>
      Sensor locations: {{ formatSourceLabel(dataStatus.sensor_location_source) }}.
      Past patterns: {{ formatSourceLabel(dataStatus.historical_profile_source) }}.
      Quiet spaces: {{ formatSourceLabel(dataStatus.refuge_source) }}.
    </p>
    <p class="data-source-line">
      {{ route.matched_sensor_count }} nearby sensor{{
        route.matched_sensor_count === 1 ? "" : "s"
      }} used for this route.
    </p>
  </section>
</template>
