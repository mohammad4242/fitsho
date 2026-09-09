import { describe, expect, it } from "vitest";

import {
  clampMediaIndex,
  resolveMediaSwipeIndex,
} from "./exerciseMediaCarousel";

describe("exercise media carousel", () => {
  it("clamps indexes safely for empty, single, and multi-item collections", () => {
    expect(clampMediaIndex(3, 0)).toBe(0);
    expect(clampMediaIndex(-4, 1)).toBe(0);
    expect(clampMediaIndex(8, 2)).toBe(1);
    expect(clampMediaIndex(0, 3)).toBe(0);
  });

  it("advances on a deliberate horizontal swipe and stays bounded", () => {
    expect(resolveMediaSwipeIndex(0, -80, 4, 2)).toBe(1);
    expect(resolveMediaSwipeIndex(1, 80, 3, 2)).toBe(0);
    expect(resolveMediaSwipeIndex(1, -80, 3, 2)).toBe(1);
    expect(resolveMediaSwipeIndex(0, 80, 3, 2)).toBe(0);
  });

  it("does not turn taps, vertical movement, or player-control gestures into swipes", () => {
    expect(resolveMediaSwipeIndex(0, -20, 0, 2)).toBe(0);
    expect(resolveMediaSwipeIndex(0, -90, 100, 2)).toBe(0);
    expect(resolveMediaSwipeIndex(1, -90, 0, 2, true)).toBe(1);
  });
});
