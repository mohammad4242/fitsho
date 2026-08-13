import { describe, expect, it, vi } from "vitest";

import {
  createMediaPipeImageSegmenterLoader,
  mediaPipeSegmentationAssets,
  MediaPipeBodySegmenter,
} from "./mediaPipeBodySegmenter";
import type { DecodedBodyPhoto } from "./processor";

const image: DecodedBodyPhoto = {
  source: {} as CanvasImageSource,
  width: 3,
  height: 2,
  decodedMimeType: "image/jpeg",
  orientationNormalized: true,
  dispose: vi.fn(),
};

describe("MediaPipeBodySegmenter", () => {
  it("copies the real person confidence mask before closing MediaPipe resources", async () => {
    const close = vi.fn();
    const values = new Float32Array([0, 0.2, 0.8, 0.9, 1, 0.5]);
    const expected = Array.from(values);
    const segmenter = new MediaPipeBodySegmenter(async () => ({
      segment: vi.fn().mockReturnValue({
        confidenceMasks: [{
          width: 3,
          height: 2,
          getAsFloat32Array: () => values,
          close,
        }],
        close,
      }),
    }));

    const result = await segmenter.segment(image);
    values.fill(0);

    expect(Array.from(result.confidence)).toEqual(expected);
    expect(result).toMatchObject({ width: 3, height: 2 });
    expect(close).toHaveBeenCalled();
  });

  it("loads the dedicated person segmenter with confidence masks", async () => {
    const createFromOptions = vi.fn().mockResolvedValue({ segment: vi.fn() });
    const loader = createMediaPipeImageSegmenterLoader(
      mediaPipeSegmentationAssets,
      async () => ({
        FilesetResolver: { forVisionTasks: vi.fn().mockResolvedValue("fileset") },
        ImageSegmenter: { createFromOptions },
      }),
    );

    await loader();

    expect(mediaPipeSegmentationAssets.modelAssetPath).toBe(
      "/mediapipe/models/selfie_segmenter.tflite",
    );
    expect(createFromOptions).toHaveBeenCalledWith("fileset", expect.objectContaining({
      outputConfidenceMasks: true,
      runningMode: "IMAGE",
    }));
  });
});
