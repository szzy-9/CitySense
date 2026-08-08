import { Capacitor } from "@capacitor/core";
import { Geolocation } from "@capacitor/geolocation";


/*
 * Demo Mode: a fixed stand-in position, for showing the app away from the CBD.
 *
 * CitySense holds data only for the Hoddle Grid and the API rejects any
 * coordinate outside it, so a device at a campus or a conference hall gets an
 * error rather than a wrong answer. With Demo Mode on, every position lookup
 * returns one CBD point instead of reading the device.
 *
 * This ships switched off, and while it is on the interface says so on every
 * screen. Somewhere between the two lies the thing this must never become: an
 * app quietly reporting a position its user is not standing in.
 */
const DEMO_STORAGE_KEY = "citysense.demoLocation";
const DEMO_WATCH_ID = "demo-origin-watch";
// Flinders Street Station, the corner most people picture when they picture
// the CBD. Override with VITE_DEMO_ORIGIN to pin Demo Mode somewhere else.
const FALLBACK_DEMO_ORIGIN = { latitude: -37.8183, longitude: 144.9671 };
const DEMO_ORIGIN =
  readDemoOrigin(import.meta.env.VITE_DEMO_ORIGIN) || FALLBACK_DEMO_ORIGIN;

let demoEnabled = readStoredDemoState();

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
  return { ...DEMO_ORIGIN };
}

export function setDemoLocationEnabled(enabled) {
  demoEnabled = Boolean(enabled);
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
      latitude: DEMO_ORIGIN.latitude,
      longitude: DEMO_ORIGIN.longitude,
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
