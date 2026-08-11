<script setup>
import { onBeforeUnmount, ref, watch } from "vue";

import { apiUrl } from "../services/api.js";
import { UserFacingError, messageForError } from "../userMessages.js";


const SEARCH_UNAVAILABLE_MESSAGE =
  "Address search is unavailable right now. Please try again shortly.";

const props = defineProps({
  fieldId: {
    type: String,
    required: true,
  },
  label: {
    type: String,
    required: true,
  },
  modelValue: {
    type: Object,
    default: null,
  },
  allowCurrentLocation: {
    type: Boolean,
    default: false,
  },
  locating: {
    type: Boolean,
    default: false,
  },
  placeholder: {
    type: String,
    default: "Search a Melbourne CBD address",
  },
});

const emit = defineEmits(["update:modelValue", "use-current-location"]);

const query = ref(props.modelValue?.label || "");
const results = ref([]);
const loading = ref(false);
const searchMessage = ref("");
let searchTimer = null;
let requestController = null;

watch(
  () => props.modelValue,
  (location) => {
    query.value = location?.label || "";
  },
);

onBeforeUnmount(() => {
  clearPendingSearch();
});

function handleInput() {
  emit("update:modelValue", null);
  results.value = [];
  searchMessage.value = "";
  clearPendingSearch();

  const text = query.value.trim();
  if (text.length < 2) {
    return;
  }

  searchTimer = window.setTimeout(() => search(text), 350);
}

async function search(text) {
  loading.value = true;
  requestController = new AbortController();
  try {
    const params = new URLSearchParams({ q: text });
    const response = await fetch(
      apiUrl(`/api/geocode/autocomplete?${params.toString()}`),
      { signal: requestController.signal },
    );
    const body = await response.json();
    if (!response.ok) {
      throw new UserFacingError(body.error || SEARCH_UNAVAILABLE_MESSAGE);
    }

    results.value = body.results || [];
    searchMessage.value = results.value.length
      ? "Select one result to confirm this location."
      : "We could not find that address in central Melbourne.";
  } catch (error) {
    if (error.name === "AbortError") {
      return;
    }
    searchMessage.value = messageForError(error, SEARCH_UNAVAILABLE_MESSAGE);
  } finally {
    loading.value = false;
  }
}

function confirmResult(result) {
  query.value = result.label;
  results.value = [];
  searchMessage.value = "Location confirmed.";
  emit("update:modelValue", result);
}

function clearPendingSearch() {
  if (searchTimer) {
    window.clearTimeout(searchTimer);
    searchTimer = null;
  }
  if (requestController) {
    requestController.abort();
    requestController = null;
  }
}
</script>

<template>
  <div class="field-group location-search">
    <label :for="fieldId">{{ label }}</label>
    <input
      :id="fieldId"
      v-model="query"
      type="search"
      autocomplete="off"
      :aria-controls="`${fieldId}-results`"
      :aria-expanded="results.length > 0"
      :aria-describedby="`${fieldId}-status`"
      :placeholder="placeholder"
      @input="handleInput"
    />

    <button
      v-if="allowCurrentLocation"
      class="current-location-button"
      type="button"
      :disabled="locating"
      @click="$emit('use-current-location')"
    >
      {{ locating ? "Getting current location..." : "Use Current Location" }}
    </button>

    <ul v-if="results.length" :id="`${fieldId}-results`" class="autocomplete-results">
      <li v-for="result in results" :key="result.id">
        <button type="button" @click="confirmResult(result)">
          {{ result.label }}
        </button>
      </li>
    </ul>

    <p :id="`${fieldId}-status`" class="location-status" aria-live="polite">
      <span v-if="loading">Searching...</span>
      <span v-else-if="modelValue" class="confirmed-location">Confirmed: {{ modelValue.label }}</span>
      <span v-else>{{ searchMessage }}</span>
    </p>
  </div>
</template>
