import { loadModuleSync } from "@expo/require-utils";
import type { ExpoConfig } from "expo/config";
import { resolve } from "node:path";

const productionApiConfig = loadModuleSync(
  resolve(__dirname, "config/productionApiConfig.ts"),
) as typeof import("./config/productionApiConfig");
type MobileRuntimeEnvironment = import("./config/productionApiConfig").MobileRuntimeEnvironment;

const withAndroidHardening = loadModuleSync(
  resolve(__dirname, "plugins/withAndroidHardening.ts"),
).default;
const withAndroidRtl = loadModuleSync(
  resolve(__dirname, "plugins/withAndroidRtl.ts"),
).default;
const withAndroidReleaseSymbols = loadModuleSync(
  resolve(__dirname, "plugins/withAndroidReleaseSymbols.ts"),
).default;
const iosHardening = loadModuleSync(
  resolve(__dirname, "plugins/withIosHardening.ts"),
) as typeof import("./plugins/withIosHardening");
const withIosHardening = iosHardening.default;

const FITICIAN_APP_LINK_PLACEHOLDER = "app.fitician.example";
const supportedAppVariants = new Set(["development", "preview", "production"]);
const appVariant = process.env.APP_VARIANT?.trim() || "development";
if (!supportedAppVariants.has(appVariant)) {
  throw new Error("APP_VARIANT must be development, preview, or production");
}

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

const isProduction = appVariant === "production";
const runtimeEnvironment = appVariant as MobileRuntimeEnvironment;
const updatesUrl = process.env.EXPO_UPDATES_URL?.trim();
const easProjectId =
  process.env.EAS_PROJECT_ID?.trim() ||
  "55951ae7-6c79-4a3a-9b89-69d4585b4667";
const googleServicesFile = process.env.GOOGLE_SERVICES_JSON?.trim();
const appLinkHost = resolveAppLinkHost(process.env.FITICIAN_APP_LINK_HOST, isProduction);
const googleAndroidClientId = process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID?.trim() || "";
const googleIosClientId = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID?.trim() || "";
for (const clientId of [googleAndroidClientId, googleIosClientId]) {
  if (clientId && !clientId.endsWith(".apps.googleusercontent.com")) {
    throw new Error("Google client IDs must use the Google OAuth client ID format");
  }
}
if (process.env.EAS_BUILD_PLATFORM === "ios" && appVariant !== "development" && !googleIosClientId) {
  throw new Error("EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID is required for iOS release builds");
}

const config: ExpoConfig = {
  name: "Fitician",
  slug: "fitician",
  version: "0.1.0",
  orientation: "portrait",
  scheme: "fitician",
  icon: "./assets/branding/fitician-icon.png",
  userInterfaceStyle: "dark",
  plugins: [
    "expo-router",
    "expo-dev-client",
    "expo-web-browser",
    "expo-apple-authentication",
    [
      "expo-splash-screen",
      {
        backgroundColor: "#020607",
        image: "./assets/branding/fitician-splash.png",
        resizeMode: "contain",
      },
    ],
    ["expo-font", fiticianFontConfig],
    "expo-secure-store",
    ["expo-sqlite", { useSQLCipher: true }],
    [
      "expo-image-picker",
      {
        cameraPermission: iosHardening.IOS_CAMERA_USAGE_DESCRIPTION,
        microphonePermission: false,
        photosPermission: false,
      },
    ],
    "expo-background-task",
    [
      "expo-notifications",
      { mode: appVariant === "development" ? "development" : "production" },
    ],
    "expo-updates",
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
    withAndroidRtl as never,
    withAndroidReleaseSymbols as never,
    withIosHardening as never,
  ],
  runtimeVersion: { policy: "appVersion" },
  updates: updatesUrl
    ? {
        checkAutomatically: "ON_ERROR_RECOVERY",
        fallbackToCacheTimeout: 0,
        url: updatesUrl,
      }
    : undefined,
  android: {
    package: "com.fitician.app",
    permissions: ["android.permission.CAMERA"],
    adaptiveIcon: {
      foregroundImage: "./assets/branding/fitician-adaptive-foreground.png",
      backgroundColor: "#020607",
    },
    ...(googleServicesFile ? { googleServicesFile } : {}),
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
    associatedDomains: [`applinks:${appLinkHost}`],
    usesAppleSignIn: true,
    infoPlist: {
      ITSAppUsesNonExemptEncryption: false,
    },
  },
  extra: {
    environment: appVariant,
    apiBaseUrl: productionApiConfig.resolveApiBaseUrl(
      process.env.EXPO_PUBLIC_API_BASE_URL,
      runtimeEnvironment,
    ),
    appLinkHost,
    frontendOrigin: productionApiConfig.resolveFrontendOrigin(
      process.env.EXPO_PUBLIC_FRONTEND_ORIGIN,
      runtimeEnvironment,
    ),
    googleAndroidClientId: googleAndroidClientId || null,
    googleIosClientId: googleIosClientId || null,
    eas: { projectId: easProjectId },
  },
};

export default config;
