import { expect, it } from "vitest";

import { formatPersianNumber } from "./locale";

it("formats native Persian numerals with explicit precision controls", () => {
  expect(formatPersianNumber(12.5, { maximumFractionDigits: 1 })).toBe("۱۲٫۵");
  expect(formatPersianNumber(7, { maximumFractionDigits: 0, useGrouping: false })).toBe("۷");
});
