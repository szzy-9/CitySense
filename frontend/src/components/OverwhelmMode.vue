<script setup>
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
  <main class="overwhelm-screen">
    <section class="overwhelm-panel" aria-labelledby="overwhelm-title">
      <p class="screen-label">Overwhelm Mode</p>
      <h1 id="overwhelm-title" data-screen-heading tabindex="-1">One next step</h1>

      <template v-if="refuge">
        <div
          class="direction-arrow"
          :style="{ transform: `rotate(${refuge.bearing_degrees}deg)` }"
          aria-hidden="true"
        >
          &uarr;
        </div>
        <p class="direction-text">Head {{ refuge.direction }}</p>
        <p class="refuge-distance">{{ refuge.distance_meters }} m</p>
        <h2>{{ refuge.name }}</h2>
        <p class="refuge-description">{{ refuge.short_description }}</p>
        <p class="basis-note">{{ calculationBasis }}</p>
        <p class="prototype-warning">{{ statusMessage }}</p>
      </template>

      <p v-else class="prototype-warning">
        We cannot find a quiet place right now. Look around you for somewhere to pause.
      </p>

      <button class="exit-button" type="button" aria-label="Exit Overwhelm Mode" @click="$emit('exit')">
        Exit
      </button>
    </section>
  </main>
</template>
