<script setup>
import { computed } from "vue";

import {
  describeUnavoidablePeak,
  formatConfidence,
  formatDataStatus,
  formatLoadLevel,
  formatSensoryIndicator,
} from "../routeDisplay.js";
import BandIcon from "./BandIcon.vue";
import PeakStrip from "./PeakStrip.vue";


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
const unavoidableNote = computed(() => describeUnavoidablePeak(props.route));
const indicator = computed(() => props.route.sensory_indicator || "NO_DATA");
const peakLevel = computed(() => props.route.sensory_level || "NO_DATA");
// The headline note already states the first reason, so listing it again just
// repeats the same sentence twice in a row.
const additionalConfidenceReasons = computed(() =>
  (props.route.confidence_reasons || []).filter(
    (reason) => reason !== props.route.confidence_explanation,
  ),
);
const prediction = computed(() => ({
  available: Boolean(props.route.historical_prediction_available),
  predictedPeak: props.route.predicted_peak || "NO_DATA",
  confidence: props.route.prediction_confidence || "LOW",
  basis: props.route.prediction_basis || "",
  reason: props.route.prediction_unavailable_reason || "",
}));
const indicatorIcon = computed(() => {
  return { LOW: "✓", HIGH: "!", NO_DATA: "?" }[indicator.value] || "?";
});
const indicatorWord = computed(() => {
  return { LOW: "Low", HIGH: "High" }[indicator.value] || "No Data";
});

function levelClass(level) {
  return "band-" + String(level || "NO_DATA").toLowerCase().replace("_", "-");
}
</script>

<template>
  <article
    class="route-card"
    :class="{ selected }"
    tabindex="0"
    :aria-label="`${role} route. ${formatSensoryIndicator(indicator)}.`"
    data-testid="route-card"
  >
    <div class="route-card-head">
      <p class="route-role">{{ role }}</p>
      <span v-if="route.recommended" class="chip">Recommended</span>
      <p class="route-source">{{ formatDataStatus(route.data_status) }}</p>
    </div>

    <p class="route-card-time">
      <span class="route-card-minutes">{{ route.duration_minutes }}</span>
      <span class="route-card-unit">min</span>
      <span class="route-card-distance">{{ distance }}</span>
    </p>

    <div v-if="route.segments?.length">
      <p class="segment-title">How busy, step by step</p>
      <PeakStrip :segments="route.segments" :peak-level="peakLevel" />
    </div>
    <p v-else class="route-detail">We have no crowd data for this route.</p>

    <dl class="route-facts">
      <div>
        <dt>Busiest point</dt>
        <dd>
          <span class="level-pill" :class="levelClass(peakLevel)">
            <BandIcon :level="peakLevel" />
            {{ formatLoadLevel(peakLevel) }}
          </span>
        </dd>
      </div>
      <div>
        <dt>How sure we are</dt>
        <dd>{{ route.confidence === "HIGH" ? "High" : "Low" }}</dd>
      </div>
      <div>
        <dt>Route checked</dt>
        <dd>{{ coverage }}%</dd>
      </div>
    </dl>

    <div
      class="sensory-indicator"
      :class="`indicator-${indicator.toLowerCase().replace('_', '-')}`"
      :aria-label="`Sensory indicator: ${formatSensoryIndicator(indicator)}`"
      data-testid="sensory-indicator"
    >
      <span class="indicator-icon" aria-hidden="true">{{ indicatorIcon }}</span>
      <span>
        <strong>{{ indicatorWord }}</strong>
        sensory indicator · {{ formatSensoryIndicator(indicator) }}
      </span>
    </div>

    <p v-if="route.recommended" class="recommended-badge" data-testid="recommended-route">
      {{
        route.congestion_avoidable
          ? "Our pick for your crowd limit"
          : "Our pick, though we cannot promise it stays calm"
      }}
    </p>

    <div class="route-detail">
      <p
        v-if="route.recommendation_reason"
        :class="{ 'not-recommended-note': !route.recommended }"
        data-testid="recommendation-reason"
      >
        {{ route.recommendation_reason }}
      </p>
      <p v-if="unavoidableNote" class="unavoidable-note" data-testid="unavoidable-peak">
        {{ unavoidableNote }}
      </p>
      <p v-if="route.peak_location">Busiest near {{ route.peak_location }}</p>
      <p>{{ route.explanation }}</p>
      <p class="confidence-note">{{ route.confidence_explanation }}</p>
      <ul v-if="additionalConfidenceReasons.length">
        <li v-for="reason in additionalConfidenceReasons" :key="reason">{{ reason }}</li>
      </ul>
      <p v-if="route.fallback_reason" class="fallback-warning">
        {{ route.fallback_reason }}
      </p>
    </div>

    <section
      class="historical-outlook"
      aria-label="What to expect"
      data-testid="historical-prediction"
    >
      <p class="segment-title">What to expect</p>
      <template v-if="prediction.available">
        <p class="prediction-value">
          <span aria-hidden="true">◷</span>
          Likely {{ formatLoadLevel(prediction.predictedPeak).toLowerCase() }}
          when you get there
        </p>
        <p>{{ formatConfidence(prediction.confidence) }} · {{ prediction.basis }}.</p>
        <p v-if="prediction.reason">{{ prediction.reason }}</p>
      </template>
      <template v-else>
        <p class="prediction-unavailable">
          <span aria-hidden="true">?</span> We cannot say how busy this will be.
        </p>
        <p v-if="prediction.reason">{{ prediction.reason }}</p>
      </template>
    </section>

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
