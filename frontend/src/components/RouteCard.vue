<script setup>
import { computed } from "vue";


const props = defineProps({
  route: {
    type: Object,
    required: true,
  },
});

const distance = computed(() => {
  const kilometres = props.route.distance_meters / 1000;
  return kilometres.toFixed(1) + " km";
});

const crowdText = computed(() => {
  if (props.route.crowd_score === null) {
    return "No nearby sensor reading";
  }
  return "Crowd score " + props.route.crowd_score;
});
</script>

<template>
  <article
    class="route-card"
    :class="{
      calmest: route.roles.includes('Calmest'),
      fastest: route.roles.includes('Fastest'),
    }"
  >
    <div class="route-card-top">
      <div class="route-badges">
        <span v-for="role in route.roles" :key="role" class="route-badge">
          {{ role }}
        </span>
        <span v-if="!route.roles.length" class="route-badge alternative">Alternative</span>
      </div>
      <span class="route-number">{{ route.id.replace("route-", "0") }}</span>
    </div>

    <div class="route-time">
      <strong>{{ route.duration_minutes }}</strong>
      <span>min</span>
    </div>

    <div class="route-metrics">
      <div>
        <span>Distance</span>
        <strong>{{ distance }}</strong>
      </div>
      <div>
        <span>Crowd estimate</span>
        <strong>{{ route.crowd_label }}</strong>
      </div>
    </div>

    <p class="sensor-note">
      {{ crowdText }} · {{ route.matched_sensor_count }} matched sensor{{
        route.matched_sensor_count === 1 ? "" : "s"
      }}
    </p>
  </article>
</template>
