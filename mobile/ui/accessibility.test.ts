import { expect, it } from "vitest";

import { fiticianTokens } from "./tokens";
import {
  ACCESSIBILITY_COLOR_PAIRS,
  ACCESSIBILITY_MIN_TOUCH_TARGET,
  contrastRatio,
  meetsContrast,
  meetsTouchTarget,
} from "./accessibility";

it("keeps the product text and status colors above WCAG normal-text contrast", () => {
  expect(ACCESSIBILITY_COLOR_PAIRS.length).toBeGreaterThan(0);
  for (const pair of ACCESSIBILITY_COLOR_PAIRS) {
    expect(meetsContrast(pair.foreground, pair.background)).toBe(true);
    expect(contrastRatio(pair.foreground, pair.background)).toBeGreaterThanOrEqual(4.5);
  }
});

it("uses a 48dp minimum touch target and rejects undersized controls", () => {
  expect(ACCESSIBILITY_MIN_TOUCH_TARGET).toBe(48);
  expect(meetsTouchTarget(48, 48)).toBe(true);
  expect(meetsTouchTarget(47, 48)).toBe(false);
  expect(meetsTouchTarget(48, 47)).toBe(false);
});

it("covers the dark Fitician canvas with the audited semantic colors", () => {
  expect(ACCESSIBILITY_COLOR_PAIRS).toEqual(expect.arrayContaining([
    { background: fiticianTokens.colors.canvas, foreground: fiticianTokens.colors.ink },
    { background: fiticianTokens.colors.canvas, foreground: fiticianTokens.colors.muted },
    { background: fiticianTokens.colors.canvas, foreground: fiticianTokens.colors.aqua },
    { background: fiticianTokens.colors.canvas, foreground: fiticianTokens.colors.coral },
    { background: fiticianTokens.colors.canvas, foreground: fiticianTokens.colors.amber },
  ]));
});
