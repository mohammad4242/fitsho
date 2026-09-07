import { describe, expect, it } from "vitest";

import {
  BODY_VISION_SPIKE_CONTRACT_VERSION,
  createBodyVisionBenchmark,
  validateNativeBodyVisionResult,
  normalizeBodyVisionResult,
} from "./nativeBodyVision";

function validPose() {
  const points = Array.from({ length: 33 }, () => ({ x: 0.5, y: 0.5, z: 0, visibility: 0.98 }));
  const pair = (left: number, right: number, y: number, span: number) => {
    points[left] = { x: 0.5 - span / 2, y, z: 0, visibility: 0.98 };
    points[right] = { x: 0.5 + span / 2, y, z: 0, visibility: 0.98 };
  };
  pair(11, 12, 0.18, 0.22);
  pair(13, 14, 0.32, 0.32);
  pair(15, 16, 0.46, 0.38);
  pair(23, 24, 0.48, 0.16);
  pair(25, 26, 0.68, 0.15);
  pair(27, 28, 0.88, 0.14);
  pair(29, 30, 0.91, 0.14);
  pair(31, 32, 0.94, 0.2);
  return points;
}

describe("native body vision spike contract", () => {
  it("normalizes native landmarks and masks without accepting raw camera pixels", () => {
    const result = normalizeBodyVisionResult({
      landmarks: [[{ x: 0.25, y: 0.5, z: -0.1, visibility: 0.9 }]],
      mask: { width: 2, height: 1, values: new Float32Array([0, 1]).buffer },
      frame: { width: 640, height: 480, timestamp: 123 },
    });

    expect(result.contractVersion).toBe(BODY_VISION_SPIKE_CONTRACT_VERSION);
    expect(result.landmarks[0]?.[0]).toEqual({
      x: 0.25,
      y: 0.5,
      z: -0.1,
      visibility: 0.9,
    });
    expect(result.mask.width).toBe(2);
    expect(result.mask.height).toBe(1);
    expect(Array.from(result.mask.confidence)).toEqual([0, 1]);
    expect(result).not.toHaveProperty("pixels");
    expect(result).not.toHaveProperty("image");
  });

  it("rejects out-of-range normalized output", () => {
    expect(() =>
      normalizeBodyVisionResult({
        landmarks: [[{ x: 1.1, y: 0.5, z: 0, visibility: 0.9 }]],
        mask: { width: 1, height: 1, values: new Float32Array([0.5]).buffer },
        frame: { width: 2, height: 2, timestamp: 1 },
      }),
    ).toThrow("normalized landmark x");
  });

  it("passes normalized native landmarks to the shared Ghost validator", () => {
    const { normalized, validation } = validateNativeBodyVisionResult(
      {
        landmarks: [validPose()],
        mask: { width: 1, height: 1, values: new Float32Array([1]).buffer },
        frame: { width: 640, height: 1800, timestamp: 123 },
      },
      { view: "front" },
    );

    expect(normalized.landmarks[0]).toHaveLength(33);
    expect(validation.status).toBe("pass");
    expect(validation.hardRejectCode).toBeNull();
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
