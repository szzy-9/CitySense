<script setup>
import { computed, onMounted, ref } from "vue";

import MapView from "./components/MapView.vue";
import RouteCard from "./components/RouteCard.vue";


const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? "http://localhost:5000" : "");

const places = ref([]);
const startId = ref("federation-square");
const endId = ref("queen-victoria-market");
const result = ref(null);
const loading = ref(false);
const errorMessage = ref("");

const startPlace = computed(() => {
  return places.value.find((place) => place.id === startId.value) || null;
});

const endPlace = computed(() => {
  return places.value.find((place) => place.id === endId.value) || null;
});

onMounted(async () => {
  await loadPlaces();
});

async function loadPlaces() {
  try {
    const response = await fetch(API_BASE_URL + "/api/places");
    if (!response.ok) {
      throw new Error("Could not load the Melbourne places.");
    }

    const body = await response.json();
    places.value = body.places;
  } catch (error) {
    errorMessage.value = "The CitySense backend is not available. Start Flask and try again.";
  }
}

async function findRoutes() {
  errorMessage.value = "";

  if (startId.value === endId.value) {
    errorMessage.value = "Choose two different places.";
    return;
  }

  loading.value = true;

  try {
    const response = await fetch(API_BASE_URL + "/api/routes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        start_id: startId.value,
        end_id: endId.value,
      }),
    });
    const body = await response.json();

    if (!response.ok) {
      throw new Error(body.error || "Could not find routes.");
    }

    result.value = body;
  } catch (error) {
    errorMessage.value = error.message || "Something went wrong. Please try again.";
  } finally {
    loading.value = false;
  }
}

function swapPlaces() {
  const previousStart = startId.value;
  startId.value = endId.value;
  endId.value = previousStart;
}

function formatUpdatedAt(value) {
  if (!value) {
    return "Not available";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Australia/Melbourne",
  }).format(date);
}
</script>

<template>
  <div class="app-shell">
    <header class="site-header">
      <a class="brand" href="#top" aria-label="CitySense home">
        <span class="brand-mark" aria-hidden="true">
          <span></span>
          <span></span>
          <span></span>
        </span>
        <span>CitySense</span>
      </a>
      <p>Melbourne on foot, at your pace.</p>
    </header>

    <main id="top">
      <section class="hero" aria-labelledby="hero-title">
        <div class="hero-copy">
          <p class="eyebrow">Walking route comparison</p>
          <h1 id="hero-title">A calmer way across the city.</h1>
          <p class="hero-intro">
            Compare a direct walk with a lower-crowd alternative, using the latest
            available City of Melbourne pedestrian data.
          </p>
        </div>

        <form class="route-form" @submit.prevent="findRoutes">
          <div class="field-group">
            <label for="start">Start</label>
            <select id="start" v-model="startId" :disabled="loading || !places.length">
              <option v-for="place in places" :key="place.id" :value="place.id">
                {{ place.name }}
              </option>
            </select>
          </div>

          <button
            class="swap-button"
            type="button"
            aria-label="Swap start and destination"
            :disabled="loading"
            @click="swapPlaces"
          >
            ⇄
          </button>

          <div class="field-group">
            <label for="destination">Destination</label>
            <select id="destination" v-model="endId" :disabled="loading || !places.length">
              <option v-for="place in places" :key="place.id" :value="place.id">
                {{ place.name }}
              </option>
            </select>
          </div>

          <button class="primary-button" type="submit" :disabled="loading || !places.length">
            <span v-if="loading" class="button-loader" aria-hidden="true"></span>
            {{ loading ? "Checking streets…" : "Compare walks" }}
          </button>
        </form>

        <p v-if="errorMessage" class="error-message" role="alert">
          {{ errorMessage }}
        </p>
      </section>

      <section class="experience" aria-label="Route map and comparison">
        <div class="map-panel">
          <MapView
            :routes="result?.routes || []"
            :start="result?.start || startPlace"
            :end="result?.end || endPlace"
          />
          <div v-if="!result" class="map-prompt">
            <span class="prompt-number">01</span>
            <div>
              <strong>Choose two places</strong>
              <p>Your two walking options will appear here.</p>
            </div>
          </div>
        </div>

        <aside class="results-panel" aria-live="polite">
          <div v-if="result" class="results-content">
            <div class="results-heading">
              <p class="eyebrow">Your options</p>
              <h2>{{ result.start.name }} → {{ result.end.name }}</h2>
            </div>

            <RouteCard
              v-for="route in result.routes"
              :key="route.id"
              :route="route"
            />

            <div class="data-status" :class="{ fallback: result.data_status.is_fallback }">
              <div class="status-heading">
                <span class="status-dot" aria-hidden="true"></span>
                <strong>
                  {{ result.data_status.is_fallback ? "Fallback active" : "Live data active" }}
                </strong>
              </div>
              <dl>
                <div>
                  <dt>Pedestrian data</dt>
                  <dd>{{ result.data_status.pedestrian_message }}</dd>
                </div>
                <div>
                  <dt>Routes</dt>
                  <dd>{{ result.data_status.route_message }}</dd>
                </div>
                <div>
                  <dt>Latest reading</dt>
                  <dd>{{ formatUpdatedAt(result.data_status.updated_at) }}</dd>
                </div>
                <div>
                  <dt>Available sensors</dt>
                  <dd>{{ result.data_status.sensor_count }}</dd>
                </div>
              </dl>
              <p v-if="result.data_status.is_fallback" class="fallback-note">
                Demo values are clearly marked and used only when a live service is unavailable.
              </p>
            </div>
          </div>

          <div v-else class="empty-results">
            <span class="prompt-number">02</span>
            <h2>Fastest or calmest?</h2>
            <p>
              CitySense keeps missing data visible. If a sensor has no reading, it is never
              quietly treated as a low-crowd street.
            </p>
            <div class="legend">
              <span><i class="line fastest"></i> Fastest</span>
              <span><i class="line calmest"></i> Calmest</span>
            </div>
          </div>
        </aside>
      </section>
    </main>

    <footer>
      <p>CitySense MVP · Walking estimates are for comparison, not turn-by-turn navigation.</p>
    </footer>
  </div>
</template>
