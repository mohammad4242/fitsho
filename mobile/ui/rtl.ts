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
  if (I18nManager.isRTL) {
    return { isRTL: true, restartRequired: false };
  }

  I18nManager.forceRTL(true);
  return { isRTL: false, restartRequired: true };
}
