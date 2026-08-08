<script setup>
/*
 * A distinct shape per load band.
 *
 * The bands are already distinguishable by colour and by word. The shape is
 * the third channel, and it is the one that survives a greyscale screenshot,
 * a bad projector, and every form of colour vision deficiency at once.
 */
defineProps({
  level: {
    type: String,
    default: "NO_DATA",
  },
  size: {
    type: Number,
    default: 14,
  },
});
</script>

<template>
  <svg
    class="band-icon"
    :width="size"
    :height="size"
    viewBox="0 0 16 16"
    aria-hidden="true"
    focusable="false"
  >
    <circle v-if="level === 'LOW'" cx="8" cy="8" r="5" fill="currentColor" />
    <path v-else-if="level === 'MODERATE'" d="M8 2 L14 8 L8 14 L2 8 Z" fill="currentColor" />
    <path v-else-if="level === 'HIGH'" d="M8 2 L15 14 L1 14 Z" fill="currentColor" />
    <rect
      v-else
      x="2"
      y="2"
      width="12"
      height="12"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-dasharray="3 2"
    />
  </svg>
</template>
