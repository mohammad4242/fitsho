import { expect, it, vi } from "vitest";

const native = vi.hoisted(() => ({
  I18nManager: {
    allowRTL: vi.fn(),
    forceRTL: vi.fn(),
    isRTL: false,
  },
}));

vi.mock("react-native", () => native);

import * as rtl from "./rtl";

import { configureFiticianRtl, FITICIAN_NATIVE_DIRECTION } from "./rtl";

it("defines one native RTL direction for the app root", () => {
  expect(FITICIAN_NATIVE_DIRECTION).toBe("rtl");
});

it("enables RTL and requests a restart when native RTL is not active", () => {
  expect(configureFiticianRtl()).toEqual({ isRTL: false, restartRequired: true });
  expect(native.I18nManager.allowRTL).toHaveBeenCalledWith(true);
  expect(native.I18nManager.forceRTL).toHaveBeenCalledWith(true);
});

it("does not request another restart after RTL is active", () => {
  native.I18nManager.isRTL = true;
  native.I18nManager.allowRTL.mockClear();
  native.I18nManager.forceRTL.mockClear();

  expect(configureFiticianRtl()).toEqual({ isRTL: true, restartRequired: false });
  expect(native.I18nManager.allowRTL).toHaveBeenCalledWith(true);
  expect(native.I18nManager.forceRTL).not.toHaveBeenCalled();
});

it("maps the existing native direction to the card language", () => {
  const languageForDirection = (rtl as unknown as {
    languageForDirection?: (isRTL: boolean) => string;
  }).languageForDirection;
  expect(typeof languageForDirection).toBe("function");
  if (languageForDirection === undefined) return;

  expect(languageForDirection(true)).toBe("fa");
  expect(languageForDirection(false)).toBe("en");
});
