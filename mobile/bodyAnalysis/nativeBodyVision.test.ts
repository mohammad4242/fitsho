import { describe, expect, it } from "vitest";

import {
  BODY_VISION_SPIKE_CONTRACT_VERSION,
  createBodyVisionBenchmark,
  normalizeBodyVisionResult,
} from "./nativeBodyVision";

describe("native body vision spike contract", () => {
  it("normalizes native landmarks and masks without accepting raw camera pixels", () => {
    const result = normalizeBodyVisionResult({
      landmarks: [[{ x: 0.25, y: 0.5, z: -0.1, visibility: 0.9 }]],
      mask: { width: 2, height: 1, values: [0, 1] },
      frame: { width: 640, height: 480, timestamp: 123 },
    });

    expect(result.contractVersion).toBe(BODY_VISION_SPIKE_CONTRACT_VERSION);
    expect(result.landmarks[0]?.[0]).toEqual({
      x: 0.25,
      y: 0.5,
      z: -0.1,
      visibility: 0.9,
    });
    expect(result.mask).toEqual({ width: 2, height: 1, values: [0, 1] });
    expect(result).not.toHaveProperty("pixels");
    expect(result).not.toHaveProperty("image");
  });

  it("rejects out-of-range normalized output", () => {
    expect(() =>
      normalizeBodyVisionResult({
        landmarks: [[{ x: 1.1, y: 0.5, z: 0, visibility: 0.9 }]],
        mask: { width: 1, height: 1, values: [0.5] },
        frame: { width: 2, height: 2, timestamp: 1 },
      }),
    ).toThrow("normalized landmark x");
  });

  it("benchmarks only the normalized result path", () => {
    const benchmark = createBodyVisionBenchmark({
      frames: [
        { durationMs: 4, result: { landmarkCount: 33, maskWidth: 16, maskHeight: 16 } },
        { durationMs: 6, result: { landmarkCount: 33, maskWidth: 16, maskHeight: 16 } },
      ],
    });

    expect(benchmark).toEqual({
      contractVersion: BODY_VISION_SPIKE_CONTRACT_VERSION,
      frameCount: 2,
      processedFrameCount: 2,
      droppedFrameCount: 0,
      averageFrameDurationMs: 5,
      maxFrameDurationMs: 6,
      landmarkCount: 33,
      maskSize: { width: 16, height: 16 },
      rawPixelsObserved: false,
    });
  });
});
