<script setup>
import { computed } from "vue";

import { formatLoadLevel, haversineDistanceMeters } from "../routeDisplay.js";

/*
 * The route drawn as the blocks you actually walk.
 *
 * This is the argument of the whole app in one control. Every other navigation
 * tool would show this trip as a single number. Here each stretch of the walk
 * gets a cell, sized by how long it is and filled by how loud it is, and the
 * worst one is marked. You can see at a glance that a route is mostly calm
 * with one terrible corner, which is exactly the shape a total or an average
 * destroys.
 */

const FILL = {
  LOW: 0.3,
  MODERATE: 0.62,
  HIGH: 1,
  NO_DATA: 1,
};

const props = defineProps({
  segments: {
    type: Array,
    default: () => [],
  },
  // The route's worst observed band. The first segment that reaches it is the
  // peak. NO_DATA is an absence of a reading, never a peak, so it marks
  // nothing.
  peakLevel: {
    type: String,
    default: "NO_DATA",
  },
  height: {
    type: Number,
    default: 44,
  },
});

const cells = computed(() => {
  let peakTaken = props.peakLevel === "NO_DATA";

  return props.segments.map((segment, index) => {
    const level = segment.sensory_level || "NO_DATA";
    const isPeak = !peakTaken && level === props.peakLevel;
    if (isPeak) {
      peakTaken = true;
    }

    return {
      key: segment.id || `segment-${index}`,
      level,
      isPeak,
      // A segment with no geometry still deserves an equal share of the strip
      // rather than collapsing to nothing.
      grow: Math.max(segmentLength(segment), 40),
      fill: `${(FILL[level] ?? 1) * 100}%`,
      bandClass: `band-${level.toLowerCase().replace("_", "-")}`,
    };
  });
});

const summary = computed(() => {
  if (!cells.value.length) {
    return "";
  }

  const blocks = cells.value
    .map((cell, index) => `Block ${index + 1} ${formatLoadLevel(cell.level)}`)
    .join(", ");
  const peak = cells.value.find((cell) => cell.isPeak);
  const worst = peak
    ? ` Worst point ${formatLoadLevel(peak.level)} at block ${cells.value.indexOf(peak) + 1}.`
    : "";

  return `Route profile, ${cells.value.length} blocks. ${blocks}.${worst}`;
});

function segmentLength(segment) {
  const coordinates = segment.geometry?.coordinates;
  if (!Array.isArray(coordinates) || coordinates.length < 2) {
    return 0;
  }

  let total = 0;
  for (let index = 0; index < coordinates.length - 1; index += 1) {
    total += haversineDistanceMeters(coordinates[index], coordinates[index + 1]);
  }
  return total;
}
</script>

<template>
  <div v-if="cells.length" class="peak-strip" role="img" :aria-label="summary">
    <div class="peak-strip-track" :style="{ height: `${height}px` }">
      <div
        v-for="cell in cells"
        :key="cell.key"
        class="peak-cell"
        :class="[cell.bandClass, { 'is-peak': cell.isPeak }]"
        :style="{ flexGrow: cell.grow }"
      >
        <div class="peak-cell-fill" :style="{ height: cell.fill }"></div>
      </div>
    </div>
    <div class="peak-strip-markers" aria-hidden="true">
      <div
        v-for="cell in cells"
        :key="`${cell.key}-marker`"
        class="peak-marker-slot"
        :style="{ flexGrow: cell.grow }"
      >
        <span v-if="cell.isPeak" class="peak-marker"></span>
      </div>
    </div>
  </div>
</template>
