import endpointConfig from "./productionApiEndpoints.json";

export type MobileRuntimeEnvironment = "development" | "preview" | "production";

// The backend is currently HTTP-only. This is still tailnet-only traffic: the
// Tailscale transport encrypts it between the Android device and this host.
export const TAILSCALE_BACKEND_HOST = endpointConfig.tailscaleBackendHost;
export const PRODUCTION_API_BASE_URL = `http://${TAILSCALE_BACKEND_HOST}:${endpointConfig.backendPort}`;
export const PRODUCTION_FRONTEND_ORIGIN = `http://${TAILSCALE_BACKEND_HOST}:${endpointConfig.frontendPort}`;

function normalizedString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

function normalizedUrl(value: string, label: string): string {
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error(`${label} must be a valid HTTP(S) URL`);
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error(`${label} must use HTTP(S)`);
  }
  if (!parsed.hostname || parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error(`${label} must not contain credentials, query parameters, or fragments`);
  }
  return value.replace(/\/+$/u, "");
}

function requireConfiguredUrl(
  value: unknown,
  environment: MobileRuntimeEnvironment,
  label: string,
  fallback?: string,
): string {
  const configured = normalizedString(value) ?? fallback ?? null;
  if (configured === null) {
    const target = environment === "production" ? ` and must be the Tailscale value ${PRODUCTION_API_BASE_URL}` : "";
    throw new Error(`${label} is required for ${environment} builds${target}`);
  }
  return normalizedUrl(configured, label);
}

export function resolveApiBaseUrl(
  value: unknown,
  environment: MobileRuntimeEnvironment,
): string {
  if (environment === "production") {
    const configured = requireConfiguredUrl(value, environment, "EXPO_PUBLIC_API_BASE_URL");
    if (configured !== PRODUCTION_API_BASE_URL) {
      throw new Error(
        `EXPO_PUBLIC_API_BASE_URL must equal the configured Tailscale backend ${PRODUCTION_API_BASE_URL}`,
      );
    }
    return configured;
  }

  if (environment === "preview") {
    const configured = requireConfiguredUrl(value, environment, "EXPO_PUBLIC_API_BASE_URL");
    if (!configured.startsWith("https://")) {
      throw new Error("EXPO_PUBLIC_API_BASE_URL must use HTTPS for preview builds");
    }
    return configured;
  }

  return requireConfiguredUrl(
    value,
    environment,
    "EXPO_PUBLIC_API_BASE_URL",
    PRODUCTION_API_BASE_URL,
  );
}

export function resolveFrontendOrigin(
  value: unknown,
  environment: MobileRuntimeEnvironment,
): string {
  if (environment === "production") {
    const configured = requireConfiguredUrl(value, environment, "EXPO_PUBLIC_FRONTEND_ORIGIN");
    if (configured !== PRODUCTION_FRONTEND_ORIGIN) {
      throw new Error(
        `EXPO_PUBLIC_FRONTEND_ORIGIN must equal the configured Tailscale origin ${PRODUCTION_FRONTEND_ORIGIN}`,
      );
    }
    return configured;
  }

  if (environment === "preview") {
    const configured = requireConfiguredUrl(value, environment, "EXPO_PUBLIC_FRONTEND_ORIGIN");
    if (!configured.startsWith("https://")) {
      throw new Error("EXPO_PUBLIC_FRONTEND_ORIGIN must use HTTPS for preview builds");
    }
    return configured;
  }

  return requireConfiguredUrl(
    value,
    environment,
    "EXPO_PUBLIC_FRONTEND_ORIGIN",
    PRODUCTION_FRONTEND_ORIGIN,
  );
}
