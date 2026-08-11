<script setup>
import ToleranceSlider from "./ToleranceSlider.vue";

defineProps({
  modelValue: {
    type: Number,
    required: true,
  },
});

defineEmits(["update:modelValue", "enter"]);
</script>

<template>
  <div class="home">
    <main id="main" class="home-inner">
      <div class="home-brand">
        <h1 class="home-wordmark" data-screen-heading tabindex="-1">
          CitySense<span class="home-mark" aria-hidden="true"></span>
        </h1>
        <p class="home-slogan">CitySense travels through the city with you.</p>
      </div>

     

      <ToleranceSlider
        :model-value="modelValue"
        @update:model-value="$emit('update:modelValue', $event)"
      />

      <button
        class="primary-button"
        type="button"
        data-testid="home-enter"
        @click="$emit('enter')"
      >
        Plan a route
      </button>

      <p class="home-note">You can change this at any time while planning.</p>
    </main>
  </div>
</template>
