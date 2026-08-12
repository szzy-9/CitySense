/*
 * The routes render below the plan form, off the bottom of a phone screen. A
 * walker who presses Find Routes and sees the form sit still has no way to
 * know anything was found, so the comparison is brought up to them.
 *
 * jsdom has no layout, so nothing here can prove pixels moved. What it can
 * prove is that the scroll is asked for, asked for on the routes section
 * rather than some other element, and not asked for when there is nothing to
 * show.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";

import routePayload from "./fixtures/neon-route-payload.json";

vi.mock("../src/services/location.js", () => ({
  isLocationSupported: () => true,
  isDemoLocationActive: () => false,
  setDemoLocationEnabled: () => false,
  demoLocationOrigin: () => ({ latitude: -37.8183, longitude: 144.9671 }),
  getCurrentPosition: async () => ({
    coords: { latitude: -37.8183, longitude: 144.9671, accuracy: 8 },
  }),
  watchPosition: async () => 1,
  clearWatch: async () => {},
}));

const COORDINATES = routePayload.routes[0].geometry.coordinates;
let scrollIntoView = null;

function locationAt([lon, lat], label) {
  return { label, lat, lon, source: "autocomplete" };
}

function jsonResponse(body) {
  return { ok: true, json: async () => body };
}

function stubFetch(routesResponse = jsonResponse(routePayload)) {
  return vi.fn(async (url, options) => {
    const path = String(url);
    if (path.includes("/api/routes") && options?.method === "POST") {
      return routesResponse;
    }
    if (path.includes("/api/refuges")) {
      return jsonResponse({ refuges: [], nearest_refuge: null });
    }
    return jsonResponse({});
  });
}

/* Fill in both ends of a trip and press Find Routes, and nothing further. */
async function planTrip() {
  const { default: App } = await import("../src/App.vue");
  const { default: LocationSearch } = await import(
    "../src/components/LocationSearch.vue"
  );

  const wrapper = mount(App, {
    global: { stubs: { MapView: true } },
    attachTo: document.body,
  });
  await flushPromises();

  await wrapper.find('[data-testid="home-enter"]').trigger("click");
  await flushPromises();

  const searches = wrapper.findAllComponents(LocationSearch);
  searches[0].vm.$emit(
    "update:modelValue",
    locationAt(COORDINATES[0], "Flinders Street Station"),
  );
  searches[1].vm.$emit(
    "update:modelValue",
    locationAt(COORDINATES[COORDINATES.length - 1], "Melbourne Museum"),
  );
  await flushPromises();

  await wrapper.find("form").trigger("submit");
  await flushPromises();

  return wrapper;
}

describe("bringing found routes into view", () => {
  beforeEach(() => {
    window.localStorage.clear();
    scrollIntoView = vi.fn();
    // jsdom does not implement it, so the app's own guard would skip the call.
    Element.prototype.scrollIntoView = scrollIntoView;
    vi.stubGlobal("fetch", stubFetch());
  });

  afterEach(() => {
    delete Element.prototype.scrollIntoView;
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("scrolls the route comparison into view once routes come back", async () => {
    const wrapper = await planTrip();

    const section = wrapper.get('[data-testid="routes-section"]').element;
    expect(scrollIntoView).toHaveBeenCalled();
    expect(scrollIntoView.mock.instances[0]).toBe(section);
    expect(scrollIntoView.mock.calls[0][0]).toEqual({
      behavior: "smooth",
      block: "start",
    });
    wrapper.unmount();
  });

  it("jumps instead when the browser never runs the animation", async () => {
    // A backgrounded tab gets no frames, so the animated scroll never starts
    // and the walker returns to a screen that did not move.
    const wrapper = await planTrip();
    const section = wrapper.get('[data-testid="routes-section"]').element;

    await new Promise((resolve) => setTimeout(resolve, 400));

    // Filtered by element: an earlier test's pending fallback fires on its own
    // section during this wait, and is not what is being asserted here.
    const behaviours = scrollIntoView.mock.calls
      .filter((_call, index) => scrollIntoView.mock.instances[index] === section)
      .map(([options]) => options.behavior);

    expect(behaviours).toEqual(["smooth", "auto"]);
    wrapper.unmount();
  });

  it("moves without animating for a walker who asked for less motion", async () => {
    vi.stubGlobal("matchMedia", (query) => ({
      matches: query === "(prefers-reduced-motion: reduce)",
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    }));

    const wrapper = await planTrip();

    expect(scrollIntoView.mock.calls[0][0]).toEqual({
      behavior: "auto",
      block: "start",
    });
    wrapper.unmount();
  });

  it("leaves the screen alone when the search fails", async () => {
    vi.stubGlobal("fetch", stubFetch({ ok: false, status: 500, json: async () => ({}) }));

    const wrapper = await planTrip();

    // The error message sits with the form. Scrolling past it to an empty
    // comparison would hide the only thing worth reading.
    expect(wrapper.find(".error-message").exists()).toBe(true);
    expect(scrollIntoView).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
