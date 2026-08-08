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
      "We picked these places ourselves. Check them when you arrive.";
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

function formatDistance(metres) {
  if (!Number.isFinite(metres)) {
    return "Distance unavailable";
  }
  return metres < 1000
    ? `${Math.round(metres)} m straight-line distance`
    : `${(metres / 1000).toFixed(1)} km straight-line distance`;
}
</script>

<template>
  <section class="refuge-finder surface-card" aria-labelledby="refuge-finder-title">
    <div v-if="!open" class="refuge-finder-entry">
      <div>
        <p class="screen-label">Quiet places</p>
        <h2 id="refuge-finder-title">Need a nearby place to pause?</h2>
        <p>See quiet spots close by, without planning a whole route.</p>
      </div>
      <button type="button" class="secondary-button" data-testid="open-refuge-finder" @click="openFinder">
        Find a Quiet Place
      </button>
    </div>

    <div v-else data-testid="refuge-finder-results">
      <div class="refuge-finder-heading">
        <div>
          <p class="screen-label">Quiet places</p>
          <h2 id="refuge-finder-title">Quiet places nearby</h2>
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

      <div v-if="refuges.length" class="refuge-result-grid">
        <article
          v-for="refuge in refuges"
          :key="refuge.id"
          class="refuge-result"
          data-testid="refuge-result"
        >
          <p class="refuge-type">{{ refuge.refuge_type }}</p>
          <h3>{{ refuge.name }}</h3>
          <p class="refuge-distance-small">{{ formatDistance(refuge.distance_meters) }}</p>
          <p>{{ refuge.short_description }}</p>
          <p class="refuge-availability">{{ refuge.availability }}</p>
          <p class="verification-note">Chosen by us · Not officially verified</p>
        </article>
      </div>
    </div>
  </section>
</template>
