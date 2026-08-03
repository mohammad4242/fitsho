import { describe, expect, it, vi } from "vitest";

import {
  createMediaPipeFaceDetectorLoader,
  MediaPipePoseLandmarkDetector,
  mediaPipeFaceAssets,
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

describe("MediaPipePoseLandmarkDetector", () => {
  it("uses the lightweight face detector without loading the pose landmarker", async () => {
    const faceLoader = vi.fn().mockResolvedValue({
      detect: vi.fn().mockReturnValue({
        detections: [{ boundingBox: { originY: 12, height: 240 } }],
      }),
    });
    const detector = new MediaPipePoseLandmarkDetector(faceLoader);

    await expect(detector.detect(decodedImage(), "front")).resolves.toMatchObject({
      personCount: 1,
      detectedView: "front",
      faceBottomY: 0.14,
      headFullyExcluded: true,
      shouldersPreserved: true,
      clothingValidation: "unavailable",
    });
    await detector.detect(decodedImage(), "front");

    expect(faceLoader).toHaveBeenCalledOnce();
  });

  it("uses the centered face and does not treat background artwork as another person", async () => {
    const detector = new MediaPipePoseLandmarkDetector(
      vi.fn().mockResolvedValue({
        detect: vi.fn().mockReturnValue({
          detections: [
            { boundingBox: { originX: 24, width: 220, originY: 10, height: 190 } },
            { boundingBox: { originX: 480, width: 220, originY: 12, height: 240 } },
          ],
        }),
      }),
    );

    await expect(detector.detect(decodedImage(), "front")).resolves.toMatchObject({
      personCount: 1,
      faceBottomY: 252 / 1800,
      safeHeadCropY: expect.any(Number),
    });
  });

  it("uses bundled local WASM and model configuration", async () => {
    const forVisionTasks = vi.fn().mockResolvedValue("fileset");
    const createFaceDetector = vi.fn().mockResolvedValue({ detect: vi.fn() });
    const loader = createMediaPipeFaceDetectorLoader(
      mediaPipeFaceAssets,
      async () => ({
        FilesetResolver: { forVisionTasks },
        FaceDetector: { createFromOptions: createFaceDetector },
      }),
    );

    await loader();

    expect(mediaPipeFaceAssets.wasmBasePath).toBe("/mediapipe/wasm");
    expect(mediaPipeFaceAssets.modelAssetPath).toBe("/mediapipe/models/blaze_face_short_range.tflite");
    expect(forVisionTasks).toHaveBeenCalledWith(mediaPipeFaceAssets.wasmBasePath);
    expect(createFaceDetector).toHaveBeenCalledWith("fileset", expect.objectContaining({
      baseOptions: { modelAssetPath: mediaPipeFaceAssets.modelAssetPath },
    }));
  });
});
