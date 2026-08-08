import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ANDROID_API_BASE_URL,
  buildApiUrl,
  resolveApiBaseUrl,
} from "../src/services/api.js";
import {
  clearWatch,
  getCurrentPosition,
  watchPosition,
} from "../src/services/location.js";


afterEach(() => {
  vi.restoreAllMocks();
});

describe("shared API URL service", () => {
  it("uses the Render backend for Android", () => {
    expect(resolveApiBaseUrl({
      platform: "android",
      configuredBaseUrl: "",
      isDevelopment: false,
    })).toBe(ANDROID_API_BASE_URL);
  });

  it("keeps production web API requests relative", () => {
    const baseUrl = resolveApiBaseUrl({
      platform: "web",
      configuredBaseUrl: "https://example.invalid",
      isDevelopment: false,
    });

    expect(buildApiUrl("/api/health", baseUrl)).toBe("/api/health");
  });

  it("keeps the configured local web API URL and removes a trailing slash", () => {
    expect(resolveApiBaseUrl({
      platform: "web",
      configuredBaseUrl: "http://localhost:5000/",
      isDevelopment: true,
    })).toBe("http://localhost:5000");
  });
});

describe("shared web location service", () => {
  it("uses browser geolocation for current and watched positions", async () => {
    const position = {
      coords: { latitude: -37.81, longitude: 144.96, accuracy: 12 },
    };
    const clearWatchMock = vi.fn();
    const watchPositionMock = vi.fn((success) => {
      success(position);
      return 17;
    });
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: {
        getCurrentPosition: (success) => success(position),
        watchPosition: watchPositionMock,
        clearWatch: clearWatchMock,
      },
    });

    await expect(getCurrentPosition()).resolves.toBe(position);
    const onPosition = vi.fn();
    const watchId = await watchPosition({}, onPosition, vi.fn());
    expect(watchId).toBe(17);
    expect(onPosition).toHaveBeenCalledWith(position);

    await clearWatch(watchId);
    expect(clearWatchMock).toHaveBeenCalledWith(17);
  });
});
