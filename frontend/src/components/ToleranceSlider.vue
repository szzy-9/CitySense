<script setup>
import { computed } from "vue";

/*
 * The counts are the load-band boundaries the backend actually classifies by,
 * in services/scoring.py: under 15 a minute is Low, 15 to 40 inclusive is
 * Moderate, above 40 is High. They are written out here so the slider states
 * the same rule the routing applies rather than an approximation of it. If
 * those boundaries move, these move with them.
 */
const BANDS = [
  {
    tolerance: "LOW",
    name: "Low (Below 15)",
    range: "Under 15",
    spoken: "under 15 people a minute",
  },
  {
    tolerance: "MODERATE",
    name: "Moderate (15 to 40)",
    range: "15-40",
    spoken: "15 to 40 people a minute",
  },
  {
    tolerance: "HIGH",
    name: "High (Over 40)",
    range: "Over 40",
    spoken: "over 40 people a minute",
  },
];

const props = defineProps({
  modelValue: {
    type: Number,
    required: true,
  },
});

const emit = defineEmits(["update:modelValue"]);

const band = computed(() => BANDS[props.modelValue - 1]);

function onInput(event) {
  emit("update:modelValue", Number(event.target.value));
}
</script>

<template>
  <section class="tolerance" aria-labelledby="tolerance-title">
    <p class="tolerance-heading">
      <span id="tolerance-title">Crowd tolerance</span>
      <span
        class="tolerance-value"
        :class="`band-${band.tolerance.toLowerCase()}`"
      >{{ band.name }}</span>
    </p>
    <p class="tolerance-hint">
      How many people a minute a street can carry before we route you around it.
    </p>
    <div class="slider-wrap">
      <input
        id="crowd-tolerance"
        type="range"
        min="1"
        max="3"
        step="1"
        :value="modelValue"
        :aria-valuetext="`${band.name}, ${band.spoken}`"
        aria-labelledby="tolerance-title"
        @input="onInput"
      />
      <!-- Hidden from the reader because aria-valuetext already speaks the
           selected band and its count; read out as a row it would just be six
           loose words between the walker and their choice. -->
      <div class="slider-labels" aria-hidden="true">
      </div>
    </div>
  </section>
</template>
