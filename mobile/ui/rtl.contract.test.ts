import { expect, it, vi } from "vitest";

vi.mock("react-native", () => ({
  I18nManager: {
    allowRTL: vi.fn(),
    forceRTL: vi.fn(),
    isRTL: true,
  },
}));

import {
  FITICIAN_NATIVE_DIRECTION,
  LTR_CENTER_TEXT,
  LTR_LAYOUT,
  LTR_TEXT,
  RTL_CENTER_TEXT,
  RTL_LAYOUT,
  RTL_ROW,
  RTL_TEXT,
  getRowDirectionStyle,
  getTextDirectionStyle,
  logicalEnd,
  logicalStart,
} from "./rtl";

it("defines one explicit native RTL layout contract", () => {
  expect(FITICIAN_NATIVE_DIRECTION).toBe("rtl");
  expect(RTL_LAYOUT).toEqual({ direction: "rtl" });
  expect(LTR_LAYOUT).toEqual({ direction: "ltr" });
  expect(RTL_ROW).toEqual({ direction: "rtl", flexDirection: "row" });
});

it("keeps Persian and technical text direction local to the value", () => {
  expect(RTL_TEXT).toEqual({ direction: "rtl", textAlign: "auto", writingDirection: "rtl" });
  expect(RTL_CENTER_TEXT).toEqual({ direction: "rtl", textAlign: "center", writingDirection: "rtl" });
  expect(LTR_TEXT).toEqual({ direction: "ltr", textAlign: "left", writingDirection: "ltr" });
  expect(LTR_CENTER_TEXT).toEqual({ direction: "ltr", textAlign: "center", writingDirection: "ltr" });
  expect(getTextDirectionStyle("rtl")).toEqual(RTL_TEXT);
  expect(getTextDirectionStyle("ltr")).toEqual(LTR_TEXT);
  expect(getTextDirectionStyle("rtl", "center")).toEqual(RTL_CENTER_TEXT);
});

it("maps logical row edges without changing the physical row primitive", () => {
  expect(getRowDirectionStyle("rtl")).toEqual(RTL_ROW);
  expect(getRowDirectionStyle("ltr")).toEqual({ direction: "ltr", flexDirection: "row" });
  expect(logicalStart("rtl")).toBe("flex-start");
  expect(logicalEnd("rtl")).toBe("flex-end");
  expect(logicalStart("ltr")).toBe("flex-end");
  expect(logicalEnd("ltr")).toBe("flex-start");
});
