import { Capacitor } from "@capacitor/core";
import { Geolocation } from "@capacitor/geolocation";


function webGeolocation() {
  return globalThis.navigator?.geolocation || null;
}

function isNativeAndroid() {
  return Capacitor.getPlatform() === "android";
}

export function isLocationSupported() {
  return isNativeAndroid() || Boolean(webGeolocation());
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
  if (watchId === null || watchId === undefined) {
    return;
  }

  if (isNativeAndroid()) {
    await Geolocation.clearWatch({ id: String(watchId) });
    return;
  }

  webGeolocation()?.clearWatch(watchId);
}
