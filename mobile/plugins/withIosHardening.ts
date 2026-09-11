import { withInfoPlist } from "expo/config-plugins";
import type { ConfigPlugin, InfoPlist } from "expo/config-plugins";
import type { JSONValue } from "@expo/json-file";

export const IOS_CAMERA_USAGE_DESCRIPTION =
  "فیتیچیان برای ثبت عکس غذا و عکس‌های تحلیل بدن به دسترسی دوربین نیاز دارد.";

type PlistRecord = Record<string, JSONValue | undefined>;

function record(value: JSONValue | undefined): PlistRecord {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as PlistRecord
    : {};
}

function httpHost(apiBaseUrl: unknown): string | null {
  if (typeof apiBaseUrl !== "string" || apiBaseUrl.trim() === "") return null;
  try {
    const url = new URL(apiBaseUrl);
    return url.protocol === "http:" && url.hostname ? url.hostname : null;
  } catch {
    return null;
  }
}

export function applyIosHardening(
  infoPlist: InfoPlist,
  apiBaseUrl: unknown,
): InfoPlist {
  const existingTransportSecurity = record(infoPlist.NSAppTransportSecurity);
  const existingExceptionDomains = record(existingTransportSecurity.NSExceptionDomains);
  const host = httpHost(apiBaseUrl);
  const exceptionDomains = host === null
    ? existingExceptionDomains
    : {
        ...existingExceptionDomains,
        [host]: {
          ...record(existingExceptionDomains[host]),
          NSExceptionAllowsInsecureHTTPLoads: true,
          NSIncludesSubdomains: false,
        },
      };

  return {
    ...infoPlist,
    NSCameraUsageDescription: IOS_CAMERA_USAGE_DESCRIPTION,
    NSAppTransportSecurity: {
      ...existingTransportSecurity,
      NSAllowsArbitraryLoads: false,
      ...(Object.keys(exceptionDomains).length > 0
        ? { NSExceptionDomains: exceptionDomains }
        : {}),
    },
  };
}

const withIosHardening: ConfigPlugin = (config) => withInfoPlist(config, (mod) => {
  mod.modResults = applyIosHardening(mod.modResults, mod.extra?.apiBaseUrl);
  return mod;
});

export default withIosHardening;
