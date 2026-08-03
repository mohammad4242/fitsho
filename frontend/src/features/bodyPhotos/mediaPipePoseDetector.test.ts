import { describe, expect, it, vi } from "vitest";

import {
  createMediaPipePoseLandmarkLoader,
  MediaPipePoseLandmarkDetector,
  mediaPipePoseAssets,
} from "./mediaPipePoseDetector";
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
    const faceLoader = vi.fn().mockResolvedValue({
      detect: vi.fn().mockReturnValue({
        detections: [{ boundingBox: { originY: 12, height: 240 } }],
      }),
    });
    const detector = new MediaPipePoseLandmarkDetector(loader, faceLoader);

    await expect(detector.detect(decodedImage(), "front")).resolves.toMatchObject({
      personCount: 1,
      detectedView: "front",
      faceBottomY: 0.14,
      headFullyExcluded: true,
      shouldersPreserved: true,
      clothingValidation: "unavailable",
    });
    await detector.detect(decodedImage(), "front");

    expect(loader).toHaveBeenCalledOnce();
    expect(faceLoader).toHaveBeenCalledOnce();
    expect(detect).toHaveBeenCalledTimes(2);
  });

  it("uses face detection when pose face landmarks are unavailable", async () => {
    const pose = landmarks();
    pose[0] = undefined as never;
    pose[7] = undefined as never;
    pose[8] = undefined as never;
    const detector = new MediaPipePoseLandmarkDetector(
      vi.fn().mockResolvedValue({ detect: vi.fn().mockReturnValue({ landmarks: [pose] }) }),
      vi.fn().mockResolvedValue({
        detect: vi.fn().mockReturnValue({
          detections: [{ boundingBox: { originY: 20, height: 220 } }],
        }),
      }),
    );

    await expect(detector.detect(decodedImage(), "front")).resolves.toMatchObject({
      faceBottomY: 240 / 1800,
      safeHeadCropY: expect.any(Number),
      headFullyExcluded: true,
    });
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

  it("uses pinned matching WASM and model configuration", async () => {
    const forVisionTasks = vi.fn().mockResolvedValue("fileset");
    const createFromOptions = vi.fn().mockResolvedValue({ detect: vi.fn() });
    const createFaceDetector = vi.fn().mockResolvedValue({ detect: vi.fn() });
    const loader = createMediaPipePoseLandmarkLoader(
      mediaPipePoseAssets,
      async () => ({
        FilesetResolver: { forVisionTasks },
        PoseLandmarker: { createFromOptions },
        FaceDetector: { createFromOptions: createFaceDetector },
      }),
    );

    await loader();

    expect(mediaPipePoseAssets.wasmBasePath).toContain("@0.10.35/wasm");
    expect(mediaPipePoseAssets.modelAssetPath).toContain("/float16/1/");
    expect(forVisionTasks).toHaveBeenCalledWith(mediaPipePoseAssets.wasmBasePath);
    expect(createFromOptions).toHaveBeenCalledWith("fileset", expect.objectContaining({
      baseOptions: { modelAssetPath: mediaPipePoseAssets.modelAssetPath },
    }));
  });
});
