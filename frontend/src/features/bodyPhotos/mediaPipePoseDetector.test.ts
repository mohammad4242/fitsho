import { describe, expect, it, vi } from "vitest";

import { MediaPipePoseLandmarkDetector } from "./mediaPipePoseDetector";
import type { DecodedBodyPhoto } from "./processor";

function decodedImage(): DecodedBodyPhoto {
  return {
    source: {} as CanvasImageSource,
    width: 1200,
    height: 1800,
    decodedMimeType: "image/jpeg",
    orientationNormalized: true,
    dispose: vi.fn(),
  };
}

function landmarks() {
  return Array.from({ length: 33 }, (_, index) => ({
    x: index === 11 ? 0.35 : index === 12 ? 0.65 : 0.5,
    y: index === 0 || index === 7 || index === 8 ? 0.12 : index === 11 || index === 12 ? 0.25 : 0.6,
    visibility: 0.96,
  }));
}

describe("MediaPipePoseLandmarkDetector", () => {
  it("uses an injected landmarker fake without loading model assets", async () => {
    const detect = vi.fn().mockReturnValue({ landmarks: [landmarks()] });
    const loader = vi.fn().mockResolvedValue({ detect });
    const detector = new MediaPipePoseLandmarkDetector(loader);

    await expect(detector.detect(decodedImage(), "front")).resolves.toMatchObject({
      personCount: 1,
      detectedView: "front",
      headFullyExcluded: true,
      shouldersPreserved: true,
    });
    await detector.detect(decodedImage(), "front");

    expect(loader).toHaveBeenCalledOnce();
    expect(detect).toHaveBeenCalledTimes(2);
  });

  it("rejects a multiple-person result through structured detector output", async () => {
    const detector = new MediaPipePoseLandmarkDetector(
      vi.fn().mockResolvedValue({ detect: vi.fn().mockReturnValue({ landmarks: [landmarks(), landmarks()] }) }),
    );

    await expect(detector.detect(decodedImage(), "front")).resolves.toMatchObject({
      personCount: 2,
      safeHeadCropY: null,
      isSafeAndRelevant: false,
    });
  });
});
