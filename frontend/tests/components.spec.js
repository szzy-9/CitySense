import {afterEach, describe, expect, it, vi} from "vitest";
import {flushPromises, mount} from "@vue/test-utils";

import RefugeFinder from "../src/components/RefugeFinder.vue";
import RouteCard from "../src/components/RouteCard.vue";
import ToleranceSlider from "../src/components/ToleranceSlider.vue";


afterEach(() => {
  vi.restoreAllMocks();
});

describe("RouteCard sensory indicator", () => {
  it("shows text and an icon immediately without a click", () => {
    const wrapper = mount(RouteCard, {
      props: {
        route: route({sensory_indicator: "LOW"}),
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
        route: route({sensory_indicator: "HIGH", sensory_level: "HIGH"}),
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

    // The badge sentence was trimmed; the backend's reason now carries the
    // whole explanation, so that is what the card has to keep showing.
    expect(wrapper.text()).toContain("All available walking routes");
    expect(wrapper.text()).toContain("above your selected crowd limit");
  });

  it("does not print the headline confidence reason twice", () => {
    const explanation = "This is an example route, not a live one.";
    const wrapper = mount(RouteCard, {
      props: {
        route: route({
          confidence: "LOW",
          confidence_explanation: explanation,
          confidence_reasons: [explanation, "Showing sample crowd counts, not today's."],
        }),
        role: "Calmest",
      },
    });

    const occurrences = wrapper.text().split(explanation).length - 1;
    expect(occurrences).toBe(1);
    expect(wrapper.text()).toContain("Showing sample crowd counts");
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
    expect(outlook.text()).toContain("Likely moderate");
    expect(outlook.text()).toContain("Fairly confident");
    expect(outlook.text()).toContain("◷");
    expect(wrapper.text()).toContain("Busiest point");
  });

  it("shows historical prediction unavailable without a zero value", () => {
    const wrapper = mount(RouteCard, {
      props: {route: route(), role: "Fastest"},
    });

    const outlook = wrapper.get('[data-testid="historical-prediction"]');
    expect(outlook.text()).toContain("We cannot say how busy this will be");
    // A missing prediction must never render as a real "Low" reading.
    expect(outlook.text()).not.toContain("Likely low");
  });
});

describe("RefugeFinder", () => {
  it("opens without a planned route and shows type, distance, and availability", async () => {
    setGeolocation((success) => {
      success({coords: {latitude: -37.81, longitude: 144.96}});
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
    const wrapper = mount(RefugeFinder);

    await wrapper.get('[data-testid="open-refuge-finder"]').trigger("click");
    await flushPromises();

    const result = wrapper.get('[data-testid="refuge-result"]');
    expect(result.text()).toContain("Outdoor");
    expect(result.text()).toContain("120m");
    expect(result.text()).toContain("Check local conditions.");
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
      props: {confirmedOrigin},
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
      {id: "segment-1", sensory_level: "LOW"},
    ],
    ...changes,
  };
}

/*
 * The counts on this slider are the boundaries the backend routes by, in
 * services/scoring.py load_level_for_count: under 15 a minute is Low, 15 to 40
 * inclusive is Moderate, above 40 is High. A walker reading "16-40" would be
 * told the wrong thing about a street counting exactly 15, so the two shared
 * boundaries are pinned here rather than left to be rounded off later.
 */
describe("crowd tolerance slider", () => {
  it("names each band with the per-minute count the backend bands by", () => {
    const labels = [1, 2, 3].map((value) => {
      const wrapper = mount(ToleranceSlider, {props: {modelValue: value}});
      const text = wrapper.get(".tolerance-value").text();
      wrapper.unmount();
      return text;
    });

    expect(labels).toEqual([
      "Low (Below 15)",
      "Moderate (15 to 40)",
      "High (Over 40)",
    ]);
    // 15 and 40 belong to Moderate, so neither may be claimed by a neighbour.
    expect(labels[0]).not.toContain("15-");
    expect(labels[2]).not.toContain("40-");
  });

  it("speaks the count with the band, so it is not sighted-only", () => {
    const wrapper = mount(ToleranceSlider, {props: {modelValue: 1}});

    expect(wrapper.get('input[type="range"]').attributes("aria-valuetext")).toBe(
      "Low (Below 15), under 15 people a minute",
    );
  });

  it("reports the band a walker drags to", async () => {
    const wrapper = mount(ToleranceSlider, {props: {modelValue: 1}});

    await wrapper.get('input[type="range"]').setValue("3");

    expect(wrapper.emitted("update:modelValue")).toEqual([[3]]);
  });
});
