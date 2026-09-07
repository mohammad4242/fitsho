import { describe, expect, it } from "vitest";

import { normalizeBodySegmentationMask } from "./body-photos.js";

describe("shared body segmentation mask contract", () => {
  it("normalizes native Float32 ArrayBuffers and preserves confidence values", () => {
    const mask = normalizeBodySegmentationMask({
      width: 2,
      height: 2,
      values: new Float32Array([0, 0.2, 0.8, 1]).buffer,
    });

    expect(mask.width).toBe(2);
    expect(mask.height).toBe(2);
    expect(Array.from(mask.confidence)).toHaveLength(4);
    expect(mask.confidence[0]).toBe(0);
    expect(mask.confidence[1]).toBeCloseTo(0.2);
    expect(mask.confidence[2]).toBeCloseTo(0.8);
    expect(mask.confidence[3]).toBe(1);
  });

  it("rejects masks whose values do not match their dimensions", () => {
    expect(() => normalizeBodySegmentationMask({
      width: 2,
      height: 2,
      confidence: new Float32Array([1, 0]),
    })).toThrow("mask values must match its dimensions");
  });
});
