import type { ExpoConfig } from "expo/config";

import withAndroidHardening from "./plugins/withAndroidHardening.ts";

const FITICIAN_APP_LINK_PLACEHOLDER = "app.fitician.example";

const fiticianFontConfig = {
  android: {
    fonts: [
      {
        fontFamily: "Vazirmatn",
        fontDefinitions: [
          { path: "./assets/fonts/Vazirmatn-Regular.ttf", weight: 400 },
          { path: "./assets/fonts/Vazirmatn-Medium.ttf", weight: 500 },
          { path: "./assets/fonts/Vazirmatn-SemiBold.ttf", weight: 600 },
          { path: "./assets/fonts/Vazirmatn-Bold.ttf", weight: 700 },
          { path: "./assets/fonts/Vazirmatn-ExtraBold.ttf", weight: 800 },
        ],
      },
      {
        fontFamily: "Lalezar",
        fontDefinitions: [{ path: "./assets/fonts/Lalezar-Regular.otf", weight: 400 }],
      },
      {
        fontFamily: "Sora",
        fontDefinitions: [
          { path: "./assets/fonts/Sora-Regular.otf", weight: 400 },
          { path: "./assets/fonts/Sora-SemiBold.otf", weight: 600 },
          { path: "./assets/fonts/Sora-Bold.otf", weight: 700 },
          { path: "./assets/fonts/Sora-ExtraBold.otf", weight: 800 },
        ],
      },
    ],
  },
  ios: {
    fonts: [
      "./assets/fonts/Vazirmatn-Regular.ttf",
      "./assets/fonts/Vazirmatn-Medium.ttf",
      "./assets/fonts/Vazirmatn-SemiBold.ttf",
      "./assets/fonts/Vazirmatn-Bold.ttf",
      "./assets/fonts/Vazirmatn-ExtraBold.ttf",
      "./assets/fonts/Lalezar-Regular.otf",
      "./assets/fonts/Sora-Regular.otf",
      "./assets/fonts/Sora-SemiBold.otf",
      "./assets/fonts/Sora-Bold.otf",
      "./assets/fonts/Sora-ExtraBold.otf",
    ],
  },
};

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
    "expo-web-browser",
    ["expo-font", fiticianFontConfig],
    "expo-secure-store",
    ["expo-sqlite", { useSQLCipher: true }],
    [
      "expo-image-picker",
      {
        cameraPermission: "اجازه بده فیتیچیان برای ثبت عکس غذا از دوربین استفاده کند.",
        microphonePermission: false,
        photosPermission: false,
      },
    ],
    "expo-background-task",
    "expo-notifications",
    "expo-video",
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
    withAndroidHardening as never,
  ],
  android: {
    package: "com.fitician.app",
    permissions: ["android.permission.CAMERA"],
    intentFilters: [
      {
        action: "VIEW",
        autoVerify: true,
        category: ["BROWSABLE", "DEFAULT"],
        data: [{ scheme: "https", host: appLinkHost, pathPrefix: "/link" }],
      },
    ],
  },
  ios: {
    bundleIdentifier: "com.fitician.app",
  },
  extra: {
    environment: process.env.APP_VARIANT || "development",
    apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL || "http://10.0.2.2:8001",
    appLinkHost,
    frontendOrigin: process.env.EXPO_PUBLIC_FRONTEND_ORIGIN || "http://localhost:5173",
    googleAndroidClientId: process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID || null,
  },
};

export default config;
