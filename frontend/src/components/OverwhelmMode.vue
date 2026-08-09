<script setup>
/*
 * Overwhelm Mode.
 *
 * One instruction, no menu, no map, no route options, nothing to decide.
 * Someone pressing the button that got them here cannot parse a normal
 * interface, so this screen asks nothing of them except to walk. It leaves the
 * app palette behind for plain black and white, because maximum contrast is
 * worth more here than consistency.
 */
defineProps({
  refuge: {
    type: Object,
    default: null,
  },
  calculationBasis: {
    type: String,
    default: "",
  },
  statusMessage: {
    type: String,
    default: "We picked this place ourselves. Check it when you arrive.",
  },
});

defineEmits(["exit"]);
</script>

<template>
  <main class="overwhelm" aria-labelledby="overwhelm-title">
    <h1 id="overwhelm-title" class="visually-hidden" data-screen-heading tabindex="-1">
      Overwhelm Mode. One next step.
    </h1>

    <div class="overwhelm-inner">
      <template v-if="refuge">
        <div
          class="overwhelm-arrow"
          :style="{ transform: `rotate(${refuge.bearing_degrees}deg)` }"
          aria-hidden="true"
        >
          <svg viewBox="0 0 100 100" width="100%" height="100%">
            <path d="M50 8 L78 42 L60 42 L60 92 L40 92 L40 42 L22 42 Z" fill="currentColor" />
          </svg>
        </div>

        <p class="overwhelm-distance">{{ refuge.distance_meters }} m</p>
        <p class="overwhelm-name">{{ refuge.name }}</p>
        <p class="overwhelm-detail">Head {{ refuge.direction }} · {{ refuge.short_description }}</p>
        <p class="overwhelm-note">{{ calculationBasis }}</p>
        <p class="overwhelm-note">{{ statusMessage }}</p>
      </template>

      <p v-else class="overwhelm-status">
        We cannot find a quiet place right now. Look around you for somewhere to pause.
      </p>
    </div>

    <button
      class="overwhelm-exit"
      type="button"
      aria-label="Exit Overwhelm Mode"
      @click="$emit('exit')"
    >
      Exit
    </button>
  </main>
</template>
