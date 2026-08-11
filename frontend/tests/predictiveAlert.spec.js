/*
 * Walks a position along a real route and reads the screen, rather than calling
 * the selection function directly the way tests/routeDisplay.test.js does.
 *
 * The pure tests prove which stretch should be warned about. They cannot prove
 * that a position update reaches the banner, which is the part a walker
 * actually experiences and the part nobody had checked without a browser.
 *
 * The payload under fixtures/ is a real response from the Neon-backed API for
 * Flinders Street Station to Melbourne Museum: eight stretches, the first five
 * Moderate, 25.8 minutes end to end.
 */
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {flushPromises, mount} from "@vue/test-utils";

import routePayload from "./fixtures/neon-route-payload.json";

// Captured so a test can push the walker forward whenever it likes.
let pushPosition = null;

vi.mock("../src/services/location.js", () => ({
  isLocationSupported: () => true,
  isDemoLocationActive: () => false,
  setDemoLocationEnabled: () => false,
  demoLocationOrigin: () => ({latitude: -37.8183, longitude: 144.9671}),
  getCurrentPosition: async () => position(START[0], START[1]),
  watchPosition: async (_options, onPosition) => {
    pushPosition = onPosition;
    return 1;
  },
  clearWatch: async () => {},
}));

const START = routePayload.routes[0].geometry.coordinates[0];
const COORDINATES = routePayload.routes[0].geometry.coordinates;

function position(lon, lat) {
  return {coords: {latitude: lat, longitude: lon, accuracy: 8}};
}

function locationAt([lon, lat], label) {
  return {label, lat, lon, source: "autocomplete"};
}

/* Move the walker to a share of the way along the route, as a fraction. */
async function walkTo(share) {
  const index = Math.min(
    COORDINATES.length - 1,
    Math.round(share * (COORDINATES.length - 1)),
  );
  const [lon, lat] = COORDINATES[index];
  pushPosition(position(lon, lat));
  await flushPromises();
}

function stubFetch() {
  return vi.fn(async (url, options) => {
    const path = String(url);
    if (path.includes("/api/routes/monitor")) {
      return jsonResponse({
        breached: false,
        upcoming_peak: "LOW",
        affected_segment_index: null,
        message: "The road ahead stays within your crowd limit.",
      });
    }
    if (path.includes("/api/routes") && options?.method === "POST") {
      return jsonResponse(routePayload);
    }
    if (path.includes("/api/refuges")) {
      return jsonResponse({refuges: [], nearest_refuge: null});
    }
    return jsonResponse({});
  });
}

function jsonResponse(body) {
  return {ok: true, json: async () => body};
}

/*
 * Plan the trip and start walking it, leaving the app on the navigate screen
 * with a position feed attached, exactly where a walker would be.
 */
async function startNavigating(tolerance = "1") {
  const {default: App} = await import("../src/App.vue");
  const {default: LocationSearch} = await import(
    "../src/components/LocationSearch.vue"
  );

  const wrapper = mount(App, {
    global: {stubs: {MapView: true}},
    attachTo: document.body,
  });
  await flushPromises();

  // Every walker lands on the home screen first. Planning is behind it.
  await wrapper.find('[data-testid="home-enter"]').trigger("click");
  await flushPromises();

  const searches = wrapper.findAllComponents(LocationSearch);
  searches[0].vm.$emit("update:modelValue", locationAt(START, "Current Location"));
  searches[1].vm.$emit(
    "update:modelValue",
    locationAt(COORDINATES[COORDINATES.length - 1], "Melbourne Museum"),
  );
  await flushPromises();

  // A Moderate stretch only counts as above the limit for someone on Low. At
  // the default of Moderate this route is within tolerance and says nothing,
  // which is the behaviour the last test in this file pins down.
  await wrapper.find('input[type="range"]').setValue(tolerance);

  await wrapper.find("form").trigger("submit");
  await flushPromises();

  // The card's button reads "Selected route" when it is already the chosen one
  // and "Navigate this route" otherwise. Both start the trip.
  const navigate = wrapper
    .findAll("button")
    .find((button) => /Navigate this route|Selected route/.test(button.text()));
  await navigate.trigger("click");
  await flushPromises();

  return wrapper;
}

function alertText(wrapper) {
  const panel = wrapper.find('[data-testid="prediction-alert"]');
  return panel.exists() ? panel.text() : "";
}

describe("predicted crowding while walking a route (AC 2.2a, AC 2.2b)", () => {
  beforeEach(() => {
    pushPosition = null;
    // The crowd tolerance now outlives a reload, so one test's choice would
    // otherwise become the next test's starting point.
    window.localStorage.clear();
    // Only the clock is faked, so flushPromises keeps working. Pinning it to
    // the hour the fixture was captured in keeps the lead times and the
    // hour-drift wording identical no matter when the suite runs.
    vi.useFakeTimers({toFake: ["Date"]});
    vi.setSystemTime(new Date(routePayload.request_settings.departure_time));
    vi.stubGlobal("fetch", stubFetch());
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("warns about the busy stretch before the walker reaches it", async () => {
    const wrapper = await startNavigating();
    await walkTo(0);

    expect(alertText(wrapper)).toContain("Likely moderate in about 6 minutes");
    // The band name is stated in words a walker reads, never as a raw enum.
    expect(alertText(wrapper)).not.toContain("MODERATE");
    wrapper.unmount();
  });

  it("counts the lead time down as the walker gets closer", async () => {
    const wrapper = await startNavigating();
    await walkTo(0);
    expect(alertText(wrapper)).toContain("about 6 minutes");

    await walkTo(0.07);
    expect(alertText(wrapper)).toContain("about 5 minutes");

    await walkTo(0.29);
    // Under the five-minute floor a fresh warning is never raised, but one
    // already on screen keeps counting rather than vanishing when it matters.
    expect(alertText(wrapper)).toContain("about 2 minutes");
    wrapper.unmount();
  });

  it("takes the warning down once the stretch is behind the walker", async () => {
    const wrapper = await startNavigating();
    await walkTo(0);
    expect(wrapper.find('[data-testid="prediction-alert"]').exists()).toBe(true);

    await walkTo(0.5);

    expect(wrapper.find('[data-testid="prediction-alert"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("says nothing when every stretch ahead sits within the crowd limit", async () => {
    const calm = structuredClone(routePayload);
    for (const segment of calm.routes[0].segments) {
      segment.predicted_band = "LOW";
    }
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url, options) => {
        const path = String(url);
        if (path.includes("/api/routes/monitor")) {
          return jsonResponse({breached: false, upcoming_peak: "LOW", message: ""});
        }
        if (path.includes("/api/routes") && options?.method === "POST") {
          return jsonResponse(calm);
        }
        return jsonResponse({refuges: [], nearest_refuge: null});
      }),
    );

    const wrapper = await startNavigating();
    await walkTo(0);

    expect(wrapper.find('[data-testid="prediction-alert"]').exists()).toBe(false);
    wrapper.unmount();
  });
});
