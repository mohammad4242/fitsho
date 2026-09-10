import { I18nManager, type TextStyle, type ViewStyle } from "react-native";

export interface FiticianRtlConfiguration {
  readonly isRTL: boolean;
  readonly restartRequired: boolean;
}

export type MobileLanguage = "fa" | "en";
export type FiticianDirection = "rtl" | "ltr";
export type FiticianTextAlign = "right" | "left" | "center";

export const FITICIAN_NATIVE_DIRECTION: FiticianDirection = "rtl";

export const RTL_LAYOUT = {
  direction: "rtl",
} as const satisfies Pick<ViewStyle, "direction">;

export const LTR_LAYOUT = {
  direction: "ltr",
} as const satisfies Pick<ViewStyle, "direction">;

export const RTL_ROW = {
  direction: "rtl",
  flexDirection: "row",
} as const satisfies Pick<ViewStyle, "direction" | "flexDirection">;

export const RTL_TEXT = {
  textAlign: "right",
  writingDirection: "rtl",
} as const satisfies Pick<TextStyle, "textAlign" | "writingDirection">;

export const RTL_CENTER_TEXT = {
  textAlign: "center",
  writingDirection: "rtl",
} as const satisfies Pick<TextStyle, "textAlign" | "writingDirection">;

export const LTR_TEXT = {
  textAlign: "left",
  writingDirection: "ltr",
} as const satisfies Pick<TextStyle, "textAlign" | "writingDirection">;

export const LTR_CENTER_TEXT = {
  textAlign: "center",
  writingDirection: "ltr",
} as const satisfies Pick<TextStyle, "textAlign" | "writingDirection">;

export function getRowDirectionStyle(
  direction: FiticianDirection = FITICIAN_NATIVE_DIRECTION,
): Pick<ViewStyle, "direction" | "flexDirection"> {
  return { direction, flexDirection: "row" };
}

export function getTextDirectionStyle(
  direction: FiticianDirection,
  textAlign: FiticianTextAlign = direction === "rtl" ? "right" : "left",
): Pick<TextStyle, "textAlign" | "writingDirection"> {
  return { textAlign, writingDirection: direction };
}

export function logicalStart(direction: FiticianDirection = FITICIAN_NATIVE_DIRECTION) {
  return direction === "rtl" ? "flex-start" : "flex-end";
}

export function logicalEnd(direction: FiticianDirection = FITICIAN_NATIVE_DIRECTION) {
  return direction === "rtl" ? "flex-end" : "flex-start";
}

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
