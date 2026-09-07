import { I18nManager } from "react-native";

export interface FiticianRtlConfiguration {
  readonly isRTL: boolean;
  readonly restartRequired: boolean;
}

export function configureFiticianRtl(): FiticianRtlConfiguration {
  I18nManager.allowRTL(true);
  if (I18nManager.isRTL) {
    return { isRTL: true, restartRequired: false };
  }

  I18nManager.forceRTL(true);
  return { isRTL: false, restartRequired: true };
}
