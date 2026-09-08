import Constants from "expo-constants";

import { logDevelopmentDiagnostic } from "../platform/logging";
import { mobileRuntimeConfigFromExtra, type MobileRuntimeConfig } from "./runtimeConfig";

export function getMobileRuntimeConfig(): MobileRuntimeConfig {
  return mobileRuntimeConfigFromExtra(Constants.expoConfig?.extra);
}

let runtimeConfigurationLogged = false;

export function logMobileRuntimeConfiguration(
  config: MobileRuntimeConfig = getMobileRuntimeConfig(),
): void {
  if (config.environment !== "development" || runtimeConfigurationLogged) return;
  runtimeConfigurationLogged = true;

  logDevelopmentDiagnostic("runtime_configuration", "info", {
    api_base_url: config.apiBaseUrl,
    environment: config.environment,
  });

  try {
    if (new URL(config.apiBaseUrl).hostname === "10.0.2.2") {
      logDevelopmentDiagnostic("emulator_only_api_target", "warning", {
        api_base_url: config.apiBaseUrl,
        target: "android_emulator_only",
      });
    }
  } catch {
    // Runtime config validation owns malformed URL handling.
  }
}
