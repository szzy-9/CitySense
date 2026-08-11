import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  demoLocationOrigin,
  getCurrentPosition,
  setDemoLocationEnabled,
} from "../src/services/location.js";

/*
 * Demo Mode stands in for a device that cannot be in the CBD. Two things have
 * to hold at once: the stand-in must land somewhere the backend will actually
 * route from, and it must not be the same corner every time, or a demo shows
 * one street rather than the city.
 */

// backend/services/locations.py, is_within_supported_area.
const SUPPORTED_AREA = {
  latitude: [-37.86, -37.77],
  longitude: [144.92, 145.02],
};
// The Hoddle Grid rectangle Demo Mode draws from.
const GRID = {
  latitude: [-37.821, -37.8075],
  longitude: [144.95, 144.974],
};

function within(value, [low, high]) {
  return value >= low && value <= high;
}

beforeEach(() => {
  setDemoLocationEnabled(false);
});

afterEach(() => {
  setDemoLocationEnabled(false);
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("Demo Mode position", () => {
  it("draws inside the grid, and so inside the area the backend accepts", () => {
    for (let attempt = 0; attempt < 200; attempt += 1) {
      setDemoLocationEnabled(true);
      const point = demoLocationOrigin();

      expect(within(point.latitude, GRID.latitude)).toBe(true);
      expect(within(point.longitude, GRID.longitude)).toBe(true);
      expect(within(point.latitude, SUPPORTED_AREA.latitude)).toBe(true);
      expect(within(point.longitude, SUPPORTED_AREA.longitude)).toBe(true);

      setDemoLocationEnabled(false);
    }
  });

  it("reaches both corners of the grid rather than a band inside it", () => {
    // Math.random is drawn once for the latitude, then once for the longitude.
    vi.spyOn(Math, "random").mockReturnValue(0);
    setDemoLocationEnabled(true);
    expect(demoLocationOrigin()).toEqual({
      latitude: GRID.latitude[0],
      longitude: GRID.longitude[0],
    });

    setDemoLocationEnabled(false);
    vi.spyOn(Math, "random").mockReturnValue(1);
    setDemoLocationEnabled(true);
    expect(demoLocationOrigin()).toEqual({
      latitude: GRID.latitude[1],
      longitude: GRID.longitude[1],
    });
  });

  it("moves to a different point each time it is switched on", () => {
    const seen = new Set();
    for (let attempt = 0; attempt < 25; attempt += 1) {
      setDemoLocationEnabled(true);
      const point = demoLocationOrigin();
      seen.add(`${point.latitude},${point.longitude}`);
      setDemoLocationEnabled(false);
    }

    // 25 draws from a rectangle a tenth of a metre wide; a repeat means the
    // point is not being redrawn at all.
    expect(seen.size).toBe(25);
  });

  it("holds still while it stays on, so a walker does not teleport", async () => {
    setDemoLocationEnabled(true);
    const origin = demoLocationOrigin();

    const first = await getCurrentPosition();
    const second = await getCurrentPosition();

    expect(first.coords.latitude).toBe(origin.latitude);
    expect(first.coords.longitude).toBe(origin.longitude);
    expect(second.coords.latitude).toBe(origin.latitude);
    expect(second.coords.longitude).toBe(origin.longitude);
    // Switching on again is what redraws it; reading it does not.
    expect(demoLocationOrigin()).toEqual(origin);
  });

  it("stays on one point when VITE_DEMO_ORIGIN pins it", async () => {
    vi.stubEnv("VITE_DEMO_ORIGIN", "-37.8183,144.9671");
    vi.resetModules();
    const pinned = await import("../src/services/location.js");

    const points = [];
    for (let attempt = 0; attempt < 5; attempt += 1) {
      pinned.setDemoLocationEnabled(true);
      points.push(pinned.demoLocationOrigin());
      pinned.setDemoLocationEnabled(false);
    }

    expect(points).toEqual(
      Array(5).fill({ latitude: -37.8183, longitude: 144.9671 }),
    );
  });
});
