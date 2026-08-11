/*
 * The home screen exists to collect one thing before any planning starts: how
 * much crowding this walker can take. These tests check that the value it
 * collects is the value the planner then routes by, and that it survives the
 * app being closed and reopened, because someone who has told us once should
 * not have to tell us again.
 */
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {flushPromises, mount} from "@vue/test-utils";

vi.mock("../src/services/location.js", () => ({
  isLocationSupported: () => true,
  isDemoLocationActive: () => false,
  setDemoLocationEnabled: () => false,
  demoLocationOrigin: () => ({latitude: -37.8183, longitude: 144.9671}),
  getCurrentPosition: async () => {
    throw new Error("not used");
  },
  watchPosition: async () => 1,
  clearWatch: async () => {},
}));

async function mountApp() {
  const {default: App} = await import("../src/App.vue");
  const wrapper = mount(App, {global: {stubs: {MapView: true}}});
  await flushPromises();
  return wrapper;
}

beforeEach(() => {
  window.localStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ok: true, json: async () => ({refuges: []})})),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("home screen", () => {
  it("opens on the home screen, not the planner", async () => {
    const wrapper = await mountApp();

    expect(wrapper.get(".home-wordmark").text()).toBe("CitySense");
    expect(wrapper.get(".home-slogan").text()).toBe(
      "Routes scored by their worst moment",
    );
    expect(wrapper.text()).not.toContain("Where are you going?");
    wrapper.unmount();
  });

  it("starts at Moderate and names the band in words", async () => {
    const wrapper = await mountApp();

    expect(wrapper.get('input[type="range"]').element.value).toBe("2");
    expect(wrapper.get(".tolerance-value").text()).toBe("Moderate");
    wrapper.unmount();
  });

  it("carries the chosen tolerance through to the planner", async () => {
    const wrapper = await mountApp();
    await wrapper.find('input[type="range"]').setValue("1");
    await wrapper.find('[data-testid="home-enter"]').trigger("click");
    await flushPromises();

    // Past the home screen, and the planner's own slider agrees with it.
    expect(wrapper.text()).toContain("Where are you going?");
    expect(wrapper.get('input[type="range"]').element.value).toBe("1");
    expect(wrapper.get(".tolerance-value").text()).toBe("Low");
    wrapper.unmount();
  });

  it("remembers the tolerance the next time the app is opened", async () => {
    const first = await mountApp();
    await first.find('input[type="range"]').setValue("3");
    first.unmount();

    const second = await mountApp();

    expect(second.get('input[type="range"]').element.value).toBe("3");
    expect(second.get(".tolerance-value").text()).toBe("High");
    second.unmount();
  });

  /*
   * The stored value indexes a three-item scale. Anything else would route the
   * walker by an undefined tolerance, so it is not trusted.
   */
  it("falls back to Moderate when the stored tolerance is unusable", async () => {
    window.localStorage.setItem("citysense.crowdTolerance", "9");

    const wrapper = await mountApp();

    expect(wrapper.get('input[type="range"]').element.value).toBe("2");
    wrapper.unmount();
  });

  /*
   * How crowded someone can bear a street to be is not a settled fact about
   * them, so the screen that asks is shown every time, already set to the
   * answer they gave last.
   */
  it("shows the home screen again on a fresh open", async () => {
    const first = await mountApp();
    await first.find('[data-testid="home-enter"]').trigger("click");
    await flushPromises();
    expect(first.text()).toContain("Where are you going?");
    first.unmount();

    const second = await mountApp();

    expect(second.find(".home-wordmark").exists()).toBe(true);
    second.unmount();
  });
});
