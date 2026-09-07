import Constants from "expo-constants";

import { mobileRuntimeConfigFromExtra, type MobileRuntimeConfig } from "./runtimeConfig";

export function getMobileRuntimeConfig(): MobileRuntimeConfig {
  return mobileRuntimeConfigFromExtra(Constants.expoConfig?.extra);
}
