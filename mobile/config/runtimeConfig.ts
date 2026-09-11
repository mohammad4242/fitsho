import {
  resolveApiBaseUrl,
  resolveFrontendOrigin,
  type MobileRuntimeEnvironment,
} from "./productionApiConfig";

export const DEFAULT_APP_LINK_HOST = "app.fitician.example";
export type { MobileRuntimeEnvironment } from "./productionApiConfig";

export interface MobileRuntimeConfig {
  readonly appLinkHost: string;
  readonly apiBaseUrl: string;
  readonly environment: MobileRuntimeEnvironment;
  readonly frontendOrigin: string;
  readonly googleAndroidClientId: string | null;
  readonly googleIosClientId: string | null;
}

export interface MobileRuntimeExtra {
  readonly appLinkHost?: unknown;
  readonly apiBaseUrl?: unknown;
  readonly environment?: unknown;
  readonly frontendOrigin?: unknown;
  readonly googleAndroidClientId?: unknown;
  readonly googleIosClientId?: unknown;
}

function trimmedString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const result = value.trim();
  return result === "" ? null : result;
}

function runtimeEnvironment(value: unknown): MobileRuntimeEnvironment {
  if (value === undefined || value === null || value === "") return "development";
  return value === "development" || value === "preview" || value === "production"
    ? value
    : "production";
}

export function googleClientIdForPlatform(
  platform: string,
  config: Pick<MobileRuntimeConfig, "googleAndroidClientId" | "googleIosClientId">,
): string | null {
  if (platform === "android") return config.googleAndroidClientId;
  if (platform === "ios") return config.googleIosClientId;
  return null;
}

export function mobileRuntimeConfigFromExtra(
  extra: MobileRuntimeExtra | null | undefined,
): MobileRuntimeConfig {
  const appLinkHost = trimmedString(extra?.appLinkHost);
  const apiBaseUrl = trimmedString(extra?.apiBaseUrl);
  const environment = runtimeEnvironment(extra?.environment);
  const frontendOrigin = trimmedString(extra?.frontendOrigin);
  const googleAndroidClientId = trimmedString(extra?.googleAndroidClientId);
  const googleIosClientId = trimmedString(extra?.googleIosClientId);
  return {
    appLinkHost: appLinkHost ?? DEFAULT_APP_LINK_HOST,
    apiBaseUrl: resolveApiBaseUrl(apiBaseUrl ?? undefined, environment),
    environment,
    frontendOrigin: resolveFrontendOrigin(frontendOrigin ?? undefined, environment),
    googleAndroidClientId,
    googleIosClientId,
  };
}
