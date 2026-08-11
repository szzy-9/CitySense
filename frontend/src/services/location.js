import { Capacitor } from "@capacitor/core";
import { Geolocation } from "@capacitor/geolocation";


/*
 * Demo Mode: a stand-in position, for showing the app away from the CBD.
 *
 * CitySense holds data only for the Hoddle Grid and the API rejects any
 * coordinate outside it, so a device at a campus or a conference hall gets an
 * error rather than a wrong answer. With Demo Mode on, every position lookup
 * returns a CBD point instead of reading the device.
 *
 * This ships switched off, and while it is on the interface says so on every
 * screen. Somewhere between the two lies the thing this must never become: an
 * app quietly reporting a position its user is not standing in.
 */
const DEMO_STORAGE_KEY = "citysense.demoLocation";
const DEMO_WATCH_ID = "demo-origin-watch";
/*
 * The Hoddle Grid, corner to corner: Flinders Street up to La Trobe Street,
 * Spencer Street across to Spring Street. 66 of the 100 pedestrian sensors sit
 * inside this rectangle, and a point drawn anywhere in it is a median 120 m
 * from the nearest one, so a demo trip is scored on real counts rather than on
 * whatever the fallback can guess. Standing on one fixed corner every time
 * hides the thing a demo is meant to show: the same trip reads differently
 * depending on where in the grid it starts.
 */
const CBD_BOUNDS = {
  minLatitude: -37.821,
  maxLatitude: -37.8075,
  minLongitude: 144.95,
  maxLongitude: 144.974,
};
// Pin Demo Mode to one point with VITE_DEMO_ORIGIN when a run has to be
// repeatable; without it each switch-on draws a fresh corner of the grid.
const PINNED_DEMO_ORIGIN = readDemoOrigin(import.meta.env.VITE_DEMO_ORIGIN);

let demoEnabled = readStoredDemoState();
let demoOrigin = PINNED_DEMO_ORIGIN || randomCbdOrigin();

function randomCbdOrigin() {
  const { minLatitude, maxLatitude, minLongitude, maxLongitude } = CBD_BOUNDS;
  const between = (low, high) => low + Math.random() * (high - low);
  return {
    // Six decimals is about a tenth of a metre; more would be a false claim
    // about how precisely anybody is standing anywhere.
    latitude: Number(between(minLatitude, maxLatitude).toFixed(6)),
    longitude: Number(between(minLongitude, maxLongitude).toFixed(6)),
  };
}

function readDemoOrigin(value) {
  if (!value) {
    return null;
  }

  const [latitude, longitude] = String(value).split(",").map(Number);
  if (
    !Number.isFinite(latitude) ||
    !Number.isFinite(longitude) ||
    Math.abs(latitude) > 90 ||
    Math.abs(longitude) > 180
  ) {
    return null;
  }
  return { latitude, longitude };
}

function readStoredDemoState() {
  try {
    return globalThis.localStorage?.getItem(DEMO_STORAGE_KEY) === "on";
  } catch {
    // Private browsing can refuse storage. Off is the default either way.
    return false;
  }
}

export function isDemoLocationActive() {
  return demoEnabled;
}

export function demoLocationOrigin() {
  return { ...demoOrigin };
}

export function setDemoLocationEnabled(enabled) {
  const wasEnabled = demoEnabled;
  demoEnabled = Boolean(enabled);
  /*
   * A new corner of the grid per switch-on, not per lookup. The position a
   * walker is standing in has to hold still while they read a route off it;
   * redrawing it mid-trip would show them teleporting.
   */
  if (demoEnabled && !wasEnabled && !PINNED_DEMO_ORIGIN) {
    demoOrigin = randomCbdOrigin();
  }
  try {
    globalThis.localStorage?.setItem(DEMO_STORAGE_KEY, demoEnabled ? "on" : "off");
  } catch {
    // The choice simply does not survive a reload.
  }
  return demoEnabled;
}

function demoPosition() {
  return {
    coords: {
      latitude: demoOrigin.latitude,
      longitude: demoOrigin.longitude,
      accuracy: 10,
    },
    timestamp: Date.now(),
  };
}

function webGeolocation() {
  return globalThis.navigator?.geolocation || null;
}

function isNativeAndroid() {
  return Capacitor.getPlatform() === "android";
}

export function isLocationSupported() {
  return isDemoLocationActive() || isNativeAndroid() || Boolean(webGeolocation());
}

async function ensureAndroidLocationPermission() {
  const current = await Geolocation.checkPermissions();
  if (
    current.location === "granted" ||
    current.coarseLocation === "granted"
  ) {
    return;
  }

  const requested = await Geolocation.requestPermissions({
    permissions: ["location"],
  });
  if (
    requested.location !== "granted" &&
    requested.coarseLocation !== "granted"
  ) {
    throw new Error("Location permission was not granted.");
  }
}

export async function getCurrentPosition(options = {}) {
  if (isDemoLocationActive()) {
    return demoPosition();
  }

  if (isNativeAndroid()) {
    await ensureAndroidLocationPermission();
    return Geolocation.getCurrentPosition(options);
  }

  const geolocation = webGeolocation();
  if (!geolocation) {
    throw new Error("Location is not supported on this device.");
  }

  return new Promise((resolve, reject) => {
    geolocation.getCurrentPosition(resolve, reject, options);
  });
}

export async function watchPosition(options, onPosition, onError) {
  if (isDemoLocationActive()) {
    // The stand-in never moves, so one reading is the whole story.
    onPosition(demoPosition());
    return DEMO_WATCH_ID;
  }

  if (isNativeAndroid()) {
    await ensureAndroidLocationPermission();
    return Geolocation.watchPosition(options, (position, error) => {
      if (error) {
        onError?.(error);
        return;
      }
      if (position) {
        onPosition(position);
      }
    });
  }

  const geolocation = webGeolocation();
  if (!geolocation) {
    throw new Error("Location is not supported on this device.");
  }

  return geolocation.watchPosition(onPosition, onError, options);
}

export async function clearWatch(watchId) {
  if (watchId === null || watchId === undefined || watchId === DEMO_WATCH_ID) {
    return;
  }

  if (isNativeAndroid()) {
    await Geolocation.clearWatch({ id: String(watchId) });
    return;
  }

  webGeolocation()?.clearWatch(watchId);
}
