<script setup>
import { ref } from "vue";

import { apiUrl } from "../services/api.js";
import {
  getCurrentPosition,
  isLocationSupported,
} from "../services/location.js";
import { UserFacingError, messageForError } from "../userMessages.js";


const props = defineProps({
  confirmedOrigin: {
    type: Object,
    default: null,
  },
});

const root = ref(null);
const open = ref(false);
const loading = ref(false);
const message = ref("");
const refuges = ref([]);

async function openFinder() {
  open.value = true;
  refuges.value = [];
  message.value = "";

  if (!isLocationSupported()) {
    message.value = "Current Location is not supported. You can use a confirmed start location.";
    return;
  }

  loading.value = true;
  try {
    const position = await getCurrentPosition({
      enableHighAccuracy: false,
      timeout: 10000,
      maximumAge: 30000,
    });
    await loadRefuges({
      label: "Current Location",
      lat: position.coords.latitude,
      lon: position.coords.longitude,
      source: "current_location",
    });
  } catch {
    loading.value = false;
    message.value = "Location permission was not available. The rest of CitySense still works.";
  }
}

function useConfirmedOrigin() {
  if (!props.confirmedOrigin) {
    return;
  }
  loadRefuges(props.confirmedOrigin);
}

async function loadRefuges(origin) {
  loading.value = true;
  message.value = "";
  try {
    const params = new URLSearchParams({
      lat: String(origin.lat),
      lon: String(origin.lon),
      label: origin.label,
      source: origin.source,
    });
    const response = await fetch(
      apiUrl(`/api/refuges?${params.toString()}`),
    );
    const body = await response.json();
    if (!response.ok) {
      throw new UserFacingError(
        body.error || "We cannot look up quiet places right now.",
      );
    }
    refuges.value = body.refuges || [];
    message.value =
      body.data_status?.message ||
      "";
  } catch (error) {
    message.value = messageForError(
      error,
      "We cannot look up quiet places right now. Please try again shortly.",
    );
  } finally {
    loading.value = false;
  }
}

function closeFinder() {
  open.value = false;
  refuges.value = [];
  message.value = "";
}

/*
 * Open already looking somewhere in particular, rather than at whichever
 * position this component would have asked for itself. A destination warning
 * has already named the place the walker needs alternatives near, so making
 * them press through the entry card to say it again would be asking twice.
 */
function openAt(origin) {
  open.value = true;
  refuges.value = [];
  message.value = "";
  return loadRefuges(origin);
}

// root travels with the opener so a caller can bring the results onto the
// screen; a list that loads below the fold reads as a button that did nothing.
defineExpose({ openAt, closeFinder, root });

function formatDistance(metres) {
  if (!Number.isFinite(metres)) {
    return "Distance unavailable";
  }
  return metres < 1000
    ? `${Math.round(metres)}m`
    : `${(metres / 1000).toFixed(1)}km`;
}
</script>

<template>
  <section ref="root" class="refuge-finder" aria-labelledby="refuge-finder-title">
    <div v-if="!open" class="refuge-finder-entry">
      <p class="screen-label">Quiet places</p>
      <h2 id="refuge-finder-title" class="section-title">Need a nearby place to pause?</h2>
      <button
        type="button"
        class="secondary-button"
        data-testid="open-refuge-finder"
        @click="openFinder"
      >
        Find a Quiet Place
      </button>
    </div>

    <div v-else data-testid="refuge-finder-results">
      <div class="refuge-finder-heading">
        <div>
          <p class="screen-label">Quiet places</p>
          <h2 id="refuge-finder-title" class="section-title">Quiet places nearby chosen by us</h2>
        </div>
        <button type="button" class="text-button" @click="closeFinder">Close</button>
      </div>

      <p v-if="loading" aria-live="polite">Finding nearby places...</p>
      <p v-if="message" class="prototype-warning-light" role="status">{{ message }}</p>

      <button
        v-if="!loading && !refuges.length && confirmedOrigin"
        type="button"
        class="secondary-button"
        data-testid="use-confirmed-origin"
        @click="useConfirmedOrigin"
      >
        Use confirmed start location
      </button>

      <ul v-if="refuges.length" class="refuge-result-list">
        <li v-for="refuge in refuges" :key="refuge.id" class="refuge-result" data-testid="refuge-result">
          <p class="refuge-type">{{ refuge.refuge_type }}</p>
          <h3>{{ refuge.name }}</h3>
          <p class="refuge-distance-small">{{ formatDistance(refuge.distance_meters) }}</p>
          <p>{{ refuge.short_description }}</p>
          <p class="refuge-availability">{{ refuge.availability }}</p>
        </li>
      </ul>
    </div>
  </section>
</template>
