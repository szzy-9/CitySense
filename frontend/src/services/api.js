import { Capacitor } from "@capacitor/core";


export const ANDROID_API_BASE_URL =
  "https://citysense-backend-exbs.onrender.com";

export function resolveApiBaseUrl({
  platform = Capacitor.getPlatform(),
  configuredBaseUrl = import.meta.env.VITE_API_BASE_URL || "",
  isDevelopment = import.meta.env.DEV,
} = {}) {
  if (platform === "android") {
    return ANDROID_API_BASE_URL;
  }

  const configured = configuredBaseUrl.trim();
  if (isDevelopment && configured) {
    return configured.replace(/\/+$/, "");
  }

  return isDevelopment ? "http://localhost:5000" : "";
}

export function buildApiUrl(path, baseUrl = resolveApiBaseUrl()) {
  const normalisedPath = path.startsWith("/") ? path : `/${path}`;
  return `${baseUrl}${normalisedPath}`;
}

export function apiUrl(path) {
  return buildApiUrl(path);
}
