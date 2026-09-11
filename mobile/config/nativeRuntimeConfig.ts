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
}
