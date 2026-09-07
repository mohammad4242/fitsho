import type { ExpoConfig } from "expo/config";

const FITICIAN_APP_LINK_PLACEHOLDER = "app.fitician.example";

function resolveAppLinkHost(rawHost: string | undefined, isProduction: boolean): string {
  const host = rawHost?.trim() || FITICIAN_APP_LINK_PLACEHOLDER;
  if (isProduction && host === FITICIAN_APP_LINK_PLACEHOLDER) {
    throw new Error(
      "FITICIAN_APP_LINK_HOST must be set to a verified HTTPS host for production builds",
    );
  }

  if (host.includes("://") || host.includes("/") || host.includes("@")) {
    throw new Error("FITICIAN_APP_LINK_HOST must contain only a hostname");
  }

  const parsed = new URL(`https://${host}`);
  if (parsed.protocol !== "https:" || parsed.hostname !== host || parsed.port) {
    throw new Error("FITICIAN_APP_LINK_HOST must be a valid HTTPS hostname without a port");
  }
  return parsed.hostname;
}

const isProduction = process.env.APP_VARIANT === "production";
const appLinkHost = resolveAppLinkHost(process.env.FITICIAN_APP_LINK_HOST, isProduction);

const config: ExpoConfig = {
  name: "Fitician",
  slug: "fitician",
  version: "0.1.0",
  orientation: "portrait",
  scheme: "fitician",
  userInterfaceStyle: "dark",
  plugins: [
    "expo-router",
    "expo-dev-client",
    [
      "expo-build-properties",
      {
        android: {
          minSdkVersion: 24,
          compileSdkVersion: 36,
          targetSdkVersion: 36,
        },
      },
    ],
  ],
  android: {
    package: "com.fitician.app",
    intentFilters: [
      {
        action: "VIEW",
        autoVerify: true,
        category: ["BROWSABLE", "DEFAULT"],
        data: [{ scheme: "https", host: appLinkHost, pathPrefix: "/link" }],
      },
    ],
  },
  extra: {
    environment: process.env.APP_VARIANT || "development",
    apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL || "http://10.0.2.2:8001",
    appLinkHost,
  },
};

export default config;
