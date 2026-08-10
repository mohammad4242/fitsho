import { describe, expect, it } from "vitest";

import { formatTomanInput, tomanToIrr } from "./money";

describe("nutrition money", () => {
  it("normalizes grouped Persian digits as Toman and converts only at the IRR boundary", () => {
    expect(formatTomanInput("۱۲,۳۴۵,۶۷۸")).toBe("12,345,678");
    expect(tomanToIrr("12,345,678")).toBe(123_456_780);
  });

  it("keeps only whole numeric Toman input and groups digits by three", () => {
    expect(formatTomanInput("1x0000000")).toBe("10,000,000");
  });
});
