export interface MobileRuntimeConfig {
  readonly apiBaseUrl: string;
  readonly frontendOrigin: string;
  readonly googleAndroidClientId: string | null;
}

export interface MobileRuntimeExtra {
  readonly apiBaseUrl?: unknown;
  readonly frontendOrigin?: unknown;
  readonly googleAndroidClientId?: unknown;
}

const DEFAULT_RUNTIME_CONFIG: MobileRuntimeConfig = {
  apiBaseUrl: "http://10.0.2.2:8001",
  frontendOrigin: "http://localhost:5173",
  googleAndroidClientId: null,
};

function trimmedString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const result = value.trim();
  return result === "" ? null : result;
}

function withoutTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

export function mobileRuntimeConfigFromExtra(
  extra: MobileRuntimeExtra | null | undefined,
): MobileRuntimeConfig {
  const apiBaseUrl = trimmedString(extra?.apiBaseUrl);
  const frontendOrigin = trimmedString(extra?.frontendOrigin);
  const googleAndroidClientId = trimmedString(extra?.googleAndroidClientId);
  return {
    apiBaseUrl: withoutTrailingSlash(apiBaseUrl ?? DEFAULT_RUNTIME_CONFIG.apiBaseUrl),
    frontendOrigin: withoutTrailingSlash(frontendOrigin ?? DEFAULT_RUNTIME_CONFIG.frontendOrigin),
    googleAndroidClientId,
  };
}
