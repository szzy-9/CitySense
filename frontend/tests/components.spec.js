import { afterEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";

import RefugeFinder from "../src/components/RefugeFinder.vue";
import RouteCard from "../src/components/RouteCard.vue";


afterEach(() => {
  vi.restoreAllMocks();
});

describe("RouteCard sensory indicator", () => {
  it("shows text and an icon immediately without a click", () => {
    const wrapper = mount(RouteCard, {
      props: {
        route: route({ sensory_indicator: "LOW" }),
        role: "Calmest",
      },
    });

    const indicator = wrapper.get('[data-testid="sensory-indicator"]');
    expect(indicator.text()).toContain("Low sensory indicator");
    expect(indicator.text()).toContain("Within your crowd limit");
    expect(indicator.get(".indicator-icon").text()).toBe("✓");
    expect(indicator.classes()).toContain("indicator-low");
  });

  it("renders NO DATA explicitly and never as Low", () => {
    const wrapper = mount(RouteCard, {
      props: {
        route: route({
          sensory_indicator: "NO_DATA",
          sensory_level: "NO_DATA",
          peak_load: "NO_DATA",
        }),
        role: "Fastest",
      },
    });

    const indicator = wrapper.get('[data-testid="sensory-indicator"]');
    expect(indicator.text()).toContain("No Data sensory indicator");
    expect(indicator.text()).toContain("Not enough reliable data");
    expect(indicator.text()).not.toContain("Low sensory indicator");
  });

  it("shows an above-threshold HIGH indicator without expansion", () => {
    const wrapper = mount(RouteCard, {
      props: {
        route: route({ sensory_indicator: "HIGH", sensory_level: "HIGH" }),
        role: "Fastest",
      },
    });

    const indicator = wrapper.get('[data-testid="sensory-indicator"]');
    expect(indicator.text()).toContain("High sensory indicator");
    expect(indicator.text()).toContain("Above your crowd limit");
    expect(indicator.get(".indicator-icon").text()).toBe("!");
  });

  it("keeps the route and its action keyboard accessible", () => {
    const wrapper = mount(RouteCard, {
      props: {
        route: route(),
        role: "Fastest",
      },
    });

    expect(wrapper.get('[data-testid="route-card"]').attributes("tabindex")).toBe("0");
    expect(wrapper.get("button").attributes("type")).toBe("button");
    expect(wrapper.get("button").attributes("aria-label")).toContain("fastest route");
  });

  it("shows an unavoidable-congestion explanation", () => {
    const wrapper = mount(RouteCard, {
      props: {
        route: route({
          recommended: true,
          congestion_avoidable: false,
          recommendation_reason:
            "All available walking routes contain at least one segment above your selected crowd limit.",
        }),
        role: "Calmest",
      },
    });

    expect(wrapper.text()).toContain("crowd avoidance not confirmed");
    expect(wrapper.text()).toContain("All available walking routes");
  });

  it("shows an available historical prediction separately from current load", () => {
    const wrapper = mount(RouteCard, {
      props: {
        route: route({
          historical_prediction_available: true,
          predicted_peak: "MODERATE",
          predicted_count: 320,
          prediction_confidence: "MEDIUM",
          prediction_basis: "Historical median for the same weekday and hour",
        }),
        role: "Calmest",
      },
    });

    const outlook = wrapper.get('[data-testid="historical-prediction"]');
    expect(outlook.text()).toContain("Predicted peak: Moderate");
    expect(outlook.text()).toContain("MEDIUM confidence");
    expect(outlook.text()).toContain("◷");
    expect(wrapper.text()).toContain("Current observed peak");
  });

  it("shows historical prediction unavailable without a zero value", () => {
    const wrapper = mount(RouteCard, {
      props: { route: route(), role: "Fastest" },
    });

    const outlook = wrapper.get('[data-testid="historical-prediction"]');
    expect(outlook.text()).toContain("Historical prediction unavailable");
    expect(outlook.text()).not.toContain("Predicted peak: Low");
  });
});

describe("RefugeFinder", () => {
  it("opens without a planned route and shows type, straight-line distance, and disclaimer", async () => {
    setGeolocation((success) => {
      success({ coords: { latitude: -37.81, longitude: 144.96 } });
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        refuges: [
          {
            id: "nearby",
            name: "Nearby garden",
            refuge_type: "Outdoor",
            distance_meters: 120,
            short_description: "Open lawn and seating nearby",
            availability: "Check local conditions.",
          },
        ],
        data_status: {
          message: "Prototype refuge information. Check local conditions.",
        },
      }),
    }));
    const wrapper = mount(RefugeFinder, { props: { apiBaseUrl: "" } });

    await wrapper.get('[data-testid="open-refuge-finder"]').trigger("click");
    await flushPromises();

    const result = wrapper.get('[data-testid="refuge-result"]');
    expect(result.text()).toContain("Outdoor");
    expect(result.text()).toContain("120 m straight-line distance");
    expect(result.text()).toContain("Not officially verified");
  });

  it("handles denied location permission and preserves an origin fallback", async () => {
    setGeolocation((_success, error) => error(new Error("denied")));
    const confirmedOrigin = {
      label: "Confirmed start",
      lat: -37.81,
      lon: 144.96,
      source: "autocomplete",
    };
    const wrapper = mount(RefugeFinder, {
      props: { apiBaseUrl: "", confirmedOrigin },
    });

    await wrapper.get('[data-testid="open-refuge-finder"]').trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("Location permission was not available");
    expect(wrapper.find('[data-testid="use-confirmed-origin"]').exists()).toBe(true);
  });
});

function setGeolocation(handler) {
  Object.defineProperty(navigator, "geolocation", {
    configurable: true,
    value: {
      getCurrentPosition: handler,
    },
  });
}

function route(changes = {}) {
  return {
    id: "route-1",
    roles: ["Calmest", "Recommended"],
    duration_minutes: 12,
    distance_meters: 900,
    sensory_level: "LOW",
    peak_load: "LOW",
    sensory_indicator: "LOW",
    data_status: "LIVE",
    confidence: "HIGH",
    confidence_explanation: "Live data from 4 nearby sensors.",
    confidence_reasons: [],
    coverage: 0.8,
    explanation: "No observed segment is above Low.",
    recommendation_reason: "Recommended because its observed peak is within your selected crowd limit.",
    recommended: true,
    congestion_avoidable: true,
    segments: [
      { id: "segment-1", sensory_level: "LOW" },
    ],
    ...changes,
  };
}
