/*
 * AC 2.2a and AC 2.2b for the case no reroute answers: the crowd is at the
 * destination.
 *
 * The pure tests in routeDisplay.test.js prove when the warning is selected.
 * These walk the screens a person walks - plan a trip, read the banner, press
 * Navigate, walk in - because the part that failed before was not the
 * selection but the advice: the only button offered was "Check another route",
 * and no other route ends anywhere else.
 *
 * The payload is the same Neon capture the predictive tests use, with its
 * final stretch set to High so the destination is the busy part.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";

import basePayload from "./fixtures/neon-route-payload.json";

let pushPosition = null;

vi.mock("../src/services/location.js", () => ({
  isLocationSupported: () => true,
  isDemoLocationActive: () => false,
  setDemoLocationEnabled: () => false,
  demoLocationOrigin: () => ({ latitude: -37.8183, longitude: 144.9671 }),
  getCurrentPosition: async () => position(START[0], START[1]),
  watchPosition: async (_options, onPosition) => {
    pushPosition = onPosition;
    return 1;
  },
  clearWatch: async () => {},
}));

const COORDINATES = basePayload.routes[0].geometry.coordinates;
const START = COORDINATES[0];
const DEPARTURE = new Date(basePayload.request_settings.departure_time);

/* The capture ends on No Data, which is silence rather than reassurance. */
function payloadWithBusyDestination(changes = {}) {
  const payload = structuredClone(basePayload);
  const segments = payload.routes[0].segments;
  segments[segments.length - 1] = {
    ...segments[segments.length - 1],
    historical_prediction_available: true,
    predicted_band: "HIGH",
    prediction_confidence: "HIGH",
    // Inside the hour the walker actually arrives in, so the wording is not
    // complicated by the pattern-drift caveat, which has its own test.
    predicted_for: new Date(DEPARTURE.getTime() + 26 * 60_000).toISOString(),
  };
  return { ...payload, ...changes };
}

function position(lon, lat) {
  return { coords: { latitude: lat, longitude: lon, accuracy: 8 } };
}

function locationAt([lon, lat], label) {
  return { label, lat, lon, source: "autocomplete" };
}

async function walkTo(share) {
  const index = Math.min(
    COORDINATES.length - 1,
    Math.round(share * (COORDINATES.length - 1)),
  );
  const [lon, lat] = COORDINATES[index];
  pushPosition(position(lon, lat));
  await flushPromises();
}

function jsonResponse(body) {
  return { ok: true, json: async () => body };
}

let fetchCalls = [];

function stubFetch(payload) {
  return vi.fn(async (url, options) => {
    const path = String(url);
    fetchCalls.push(path);
    if (path.includes("/api/routes/monitor")) {
      return jsonResponse({
        breached: false,
        upcoming_peak: "LOW",
        affected_segment_index: null,
        message: "The road ahead stays within your crowd limit.",
      });
    }
    if (path.includes("/api/routes") && options?.method === "POST") {
      return jsonResponse(payload);
    }
    if (path.includes("/api/refuges")) {
      return jsonResponse({
        refuges: [
          {
            id: "carlton-gardens",
            name: "Carlton Gardens, north lawn",
            refuge_type: "Outdoor",
            distance_meters: 180,
            short_description: "Lawn and benches away from the entrance.",
            availability: "Open to all.",
          },
        ],
        nearest_refuge: null,
      });
    }
    return jsonResponse({});
  });
}

/* Plan the trip and stop, which is where the first warning belongs. */
async function planTrip(tolerance = "2") {
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
  searches[0].vm.$emit("update:modelValue", locationAt(START, "Current Location"));
  searches[1].vm.$emit(
    "update:modelValue",
    locationAt(COORDINATES[COORDINATES.length - 1], "Melbourne Museum"),
  );
  await flushPromises();

  await wrapper.find('input[type="range"]').setValue(tolerance);
  await wrapper.find("form").trigger("submit");
  await flushPromises();

  return wrapper;
}

async function startWalking(wrapper) {
  const navigate = wrapper
    .findAll("button")
    .find((button) => /Navigate this route|Selected route/.test(button.text()));
  await navigate.trigger("click");
  await flushPromises();
}

function alertText(wrapper) {
  const panel = wrapper.find('[data-testid="destination-alert"]');
  return panel.exists() ? panel.text() : "";
}

describe("a destination the walker cannot route around (AC 2.2a, AC 2.2b)", () => {
  beforeEach(() => {
    pushPosition = null;
    fetchCalls = [];
    window.localStorage.clear();
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(DEPARTURE);
    vi.stubGlobal("fetch", stubFetch(payloadWithBusyDestination()));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("warns before the walker sets off, while delaying is still free", async () => {
    const wrapper = await planTrip();

    expect(alertText(wrapper)).toContain("Near your destination is likely high");
    expect(alertText(wrapper)).toContain("around the time you get there");
    // The capture has congestion_avoidable false, which is the whole point:
    // saying so is what stops a reroute reading as the obvious next move.
    expect(alertText(wrapper)).toContain("No route avoids it.");
    expect(alertText(wrapper)).not.toContain("Check another route");
    // Internal band names never reach the screen.
    expect(alertText(wrapper)).not.toContain("HIGH");
    wrapper.unmount();
  });

  it("offers the later departure inside the warning, not as a separate notice", async () => {
    vi.stubGlobal(
      "fetch",
      stubFetch(
        payloadWithBusyDestination({
          departure_suggestion: {
            departure_time: new Date(DEPARTURE.getTime() + 45 * 60_000).toISOString(),
            minutes_later: 45,
            predicted_peak: "MODERATE",
            message: "Leaving 45 minutes later drops the busiest point to moderate.",
          },
        }),
      ),
    );

    const wrapper = await planTrip();

    expect(alertText(wrapper)).toContain("Leaving 45 minutes later");
    expect(
      wrapper.find('[data-testid="destination-alert"]').text(),
    ).toMatch(/Leave at .+ instead/);
    // One panel about one trip, not two stacked notices saying related things.
    expect(wrapper.find('[data-testid="departure-suggestion"]').exists()).toBe(false);
    wrapper.unmount();
  });

  it("holds off while walking until arrival is close enough to act on", async () => {
    const wrapper = await planTrip();
    await startWalking(wrapper);
    await walkTo(0);

    // Twenty-six minutes out, the walker has already chosen this destination.
    expect(alertText(wrapper)).toBe("");

    // Twelve minutes out. At 0.55 there are still sixteen, which is outside
    // the window on purpose.
    await walkTo(0.7);

    expect(alertText(wrapper)).toContain("when you arrive, in about");
    expect(alertText(wrapper)).toContain("Quiet places near there");
    // Leaving later is not a choice someone already walking still has.
    expect(alertText(wrapper)).not.toMatch(/Leave at .+ instead/);
    wrapper.unmount();
  });

  it("looks for quiet places near the destination, not near the start", async () => {
    const wrapper = await planTrip();
    await wrapper.find('[data-testid="destination-refuges"]').trigger("click");
    await flushPromises();

    // The planner also warms the refuge list with a bare call; the one that
    // matters here is the lookup that names a place.
    const refugeCall = fetchCalls.find(
      (path) => path.includes("/api/refuges") && path.includes("lat="),
    );
    expect(refugeCall).toContain("lat=-37.8033");
    expect(refugeCall).toContain("lon=144.9717");
    expect(wrapper.text()).toContain("Carlton Gardens, north lawn");
    wrapper.unmount();
  });

  it("takes the warning down once the walker has arrived", async () => {
    const wrapper = await planTrip();
    await startWalking(wrapper);
    // Twelve minutes out. At 0.55 there are still sixteen, which is outside
    // the window on purpose.
    await walkTo(0.7);
    expect(alertText(wrapper)).not.toBe("");

    // Standing on the destination itself. The route's last drawn point stops a
    // little short of it, which is not yet arrival.
    pushPosition(position(basePayload.end.lon, basePayload.end.lat));
    await flushPromises();

    expect(alertText(wrapper)).toBe("");
    wrapper.unmount();
  });

  it("says nothing to a walker whose limit the destination sits inside", async () => {
    const wrapper = await planTrip("3");

    expect(alertText(wrapper)).toBe("");
    wrapper.unmount();
  });
});
