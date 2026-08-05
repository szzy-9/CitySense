<script setup>
import { computed } from "vue";

import {
  formatDataStatus,
  formatLoadLevel,
  formatSensoryIndicator,
} from "../routeDisplay.js";
import RouteLoadBar from "./RouteLoadBar.vue";


const props = defineProps({
  route: {
    type: Object,
    required: true,
  },
  role: {
    type: String,
    required: true,
  },
  comparisonText: {
    type: String,
    default: "",
  },
  selected: {
    type: Boolean,
    default: false,
  },
  showAction: {
    type: Boolean,
    default: true,
  },
});

defineEmits(["select"]);

const distance = computed(() => {
  const metres = props.route.distance_meters;
  if (metres < 1000) {
    return `${metres} m`;
  }
  return `${(metres / 1000).toFixed(1)} km`;
});

const coverage = computed(() => Math.round((props.route.coverage || 0) * 100));
const indicator = computed(() => props.route.sensory_indicator || "NO_DATA");
const indicatorIcon = computed(() => {
  return { LOW: "✓", HIGH: "!", NO_DATA: "?" }[indicator.value] || "?";
});

function levelClass(level) {
  return "level-" + String(level || "NO_DATA").toLowerCase().replace("_", "-");
}
</script>

<template>
  <article
    class="route-card"
    :class="[{ selected }, role.toLowerCase(), levelClass(route.sensory_level)]"
    tabindex="0"
    :aria-label="`${role} route. ${formatSensoryIndicator(indicator)}.`"
    data-testid="route-card"
  >
    <div class="route-card-heading">
      <div>
        <p class="route-role">{{ role }}</p>
        <p class="route-source">{{ formatDataStatus(route.data_status) }}</p>
      </div>
      <p class="route-time"><strong>{{ route.duration_minutes }}</strong> min</p>
    </div>

    <div
      class="sensory-indicator"
      :class="`indicator-${indicator.toLowerCase().replace('_', '-')}`"
      :aria-label="`Sensory indicator: ${formatSensoryIndicator(indicator)}`"
      data-testid="sensory-indicator"
    >
      <span class="indicator-icon" aria-hidden="true">{{ indicatorIcon }}</span>
      <span>
        <strong>{{ indicator === "LOW" ? "Low" : indicator === "HIGH" ? "High" : "No Data" }}</strong>
        sensory indicator · {{ formatSensoryIndicator(indicator) }}
      </span>
    </div>

    <p v-if="route.recommended" class="recommended-badge" data-testid="recommended-route">
      {{
        route.congestion_avoidable
          ? "Recommended for your selected crowd limit"
          : "Lowest observed option; crowd avoidance not confirmed"
      }}
    </p>
    <p
      v-if="route.recommendation_reason"
      :class="route.recommended ? 'route-explanation' : 'not-recommended-note'"
      data-testid="recommendation-reason"
    >
      {{ route.recommendation_reason }}
    </p>

    <dl class="route-facts">
      <div>
        <dt>Distance</dt>
        <dd>{{ distance }}</dd>
      </div>
      <div>
        <dt>Sensory level</dt>
        <dd class="level-pill" :class="levelClass(route.sensory_level)">
          {{ formatLoadLevel(route.sensory_level) }}
        </dd>
      </div>
      <div>
        <dt>Confidence</dt>
        <dd>{{ route.confidence === "HIGH" ? "High" : "Low" }}</dd>
      </div>
      <div>
        <dt>Coverage</dt>
        <dd>{{ coverage }}%</dd>
      </div>
    </dl>

    <p v-if="route.peak_location" class="route-explanation">
      Peak location: {{ route.peak_location }}
    </p>
    <p class="route-explanation">{{ route.explanation }}</p>
    <p class="confidence-note">{{ route.confidence_explanation }}</p>
    <ul v-if="route.confidence_reasons?.length > 1" class="confidence-reasons">
      <li v-for="reason in route.confidence_reasons" :key="reason">{{ reason }}</li>
    </ul>
    <p v-if="route.fallback_reason" class="fallback-warning">
      {{ route.fallback_reason }}
    </p>

    <div v-if="route.segments?.length" class="segment-section">
      <p class="segment-title">Load by segment</p>
      <RouteLoadBar :segments="route.segments" />
    </div>
    <p v-else class="no-segments">No segment data is available.</p>

    <p v-if="comparisonText" class="comparison-note">{{ comparisonText }}</p>

    <button
      v-if="showAction"
      class="route-select-button"
      type="button"
      :aria-label="`Navigate using the ${role.toLowerCase()} route`"
      @click="$emit('select', route)"
    >
      {{ selected ? "Selected route" : "Navigate this route" }}
    </button>
  </article>
</template>
