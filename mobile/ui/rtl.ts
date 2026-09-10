import { I18nManager } from "react-native";

export interface FiticianRtlConfiguration {
  readonly isRTL: boolean;
  readonly restartRequired: boolean;
}

export type MobileLanguage = "fa" | "en";

export const FITICIAN_NATIVE_DIRECTION = "rtl" as const;

export function languageForDirection(isRTL = I18nManager.isRTL): MobileLanguage {
  return isRTL ? "fa" : "en";
}

export function configureFiticianRtl(): FiticianRtlConfiguration {
  I18nManager.allowRTL(true);
  // The Android config plugin applies this before the bridge starts. Keep the JS
  // guard unconditional so older development clients converge to the same policy.
  I18nManager.forceRTL(true);
  return { isRTL: I18nManager.isRTL, restartRequired: !I18nManager.isRTL };
}
