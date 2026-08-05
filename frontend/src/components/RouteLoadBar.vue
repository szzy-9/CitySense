<script setup>
import { formatLoadLevel } from "../routeDisplay.js";


defineProps({
  segments: {
    type: Array,
    default: () => [],
  },
});

function levelClass(level) {
  return "load-" + String(level || "NO_DATA").toLowerCase().replace("_", "-");
}
</script>

<template>
  <div class="load-bar" aria-label="Load by route segment">
    <span
      v-for="segment in segments"
      :key="segment.id"
      class="load-block"
      :class="levelClass(segment.sensory_level)"
      :aria-label="`${segment.id}: ${formatLoadLevel(segment.sensory_level)}`"
      :title="`${segment.id}: ${formatLoadLevel(segment.sensory_level)}`"
    >
      {{ formatLoadLevel(segment.sensory_level) }}
    </span>
  </div>
</template>
