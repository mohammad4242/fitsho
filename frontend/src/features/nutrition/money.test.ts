import { describe, expect, it } from "vitest";

import { formatTomanInput, irrToRoundedToman, roundToTenThousandToman, tomanToIrr } from "./money";

describe("nutrition money", () => {
  it("normalizes grouped Persian digits as Toman and converts only at the IRR boundary", () => {
    expect(formatTomanInput("۱۲,۳۴۵,۶۷۸")).toBe("12,345,678");
    expect(tomanToIrr("12,345,678")).toBe(123_456_780);
  });

  it("keeps only whole numeric Toman input and groups digits by three", () => {
    expect(formatTomanInput("1x0000000")).toBe("10,000,000");
  });

  it("rounds Toman amounts to nearest 10,000 step", () => {
    expect(roundToTenThousandToman(236_500)).toBe(240_000);
    expect(roundToTenThousandToman(521_231)).toBe(520_000);
    expect(roundToTenThousandToman(10_000)).toBe(10_000);
    expect(roundToTenThousandToman(4_000)).toBe(10_000);
    expect(roundToTenThousandToman(0)).toBe(0);
  });

  it("converts IRR to rounded Toman step", () => {
    expect(irrToRoundedToman(2_365_000)).toBe(240_000);
    expect(irrToRoundedToman(5_212_310)).toBe(520_000);
  });
});

