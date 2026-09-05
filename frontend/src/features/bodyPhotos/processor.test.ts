import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  BrowserBodyPhotoProcessor,
  BodyPhotoProcessingError,
  compositeBodyOnNeutralBackground,
  type BodyLandmarkDetection,
  type BodyLandmarkDetector,
  type BodyPhotoRuntime,
  type BodyPhotoSegmenter,
  type BodySegmentationMask,
  type DecodedBodyPhoto,
  type NormalizedBodyLandmark,
} from "./processor";

function landmarks(shape: "front" | "side" = "front"): NormalizedBodyLandmark[] {
  const points = Array.from({ length: 33 }, () => ({ x: 0.5, y: 0.5, z: 0, visibility: 0.98 }));
  const span = shape === "side" ? 0.035 : 0.22;
  const pair = (left: number, right: number, y: number, pairSpan = span) => {
    points[left] = { x: 0.5 - pairSpan / 2, y, z: 0, visibility: 0.98 };
    points[right] = { x: 0.5 + pairSpan / 2, y, z: 0, visibility: 0.98 };
  };
  pair(11, 12, 0.08);
  pair(13, 14, 0.25, shape === "side" ? 0.08 : 0.32);
  pair(15, 16, 0.42, shape === "side" ? 0.1 : 0.38);
  pair(23, 24, 0.43, shape === "side" ? 0.03 : 0.16);
  pair(25, 26, 0.68, shape === "side" ? 0.04 : 0.15);
  pair(27, 28, 0.9, shape === "side" ? 0.04 : 0.14);
  pair(29, 30, 0.92, shape === "side" ? 0.04 : 0.14);
  pair(31, 32, 0.95, shape === "side" ? 0.08 : 0.2);
  return points;
}

function inputFile() {
  return new File([new Uint8Array([0xff, 0xd8, 0xff, 0xdb])], "headless.jpg", {
    type: "image/jpeg",
  });
}

function translatedPose(pose: NormalizedBodyLandmark[], deltaX: number) {
  return pose.map((point) => ({ ...point, x: point.x + deltaX }));
}

function setup(options: {
  viewShape?: "front" | "side";
  poses?: NormalizedBodyLandmark[][];
  mutate?: (value: NormalizedBodyLandmark[]) => void;
  width?: number;
  height?: number;
  brightness?: number;
  sharpness?: number;
  orientationNormalized?: boolean;
  mask?: BodySegmentationMask;
} = {}) {
  const detected = landmarks(options.viewShape);
  options.mutate?.(detected);
  const detection: BodyLandmarkDetection = {
    poses: options.poses ?? [detected],
  };
  const detector: BodyLandmarkDetector = { detect: vi.fn().mockResolvedValue(detection) };
  const segmenter: BodyPhotoSegmenter = {
    segment: vi.fn().mockResolvedValue({
      width: options.mask?.width ?? 2,
      height: options.mask?.height ?? 2,
      confidence: options.mask?.confidence ?? new Float32Array([0, 1, 1, 0]),
    }),
  };
  const decoded: DecodedBodyPhoto = {
    source: {} as CanvasImageSource,
    width: options.width ?? 1200,
    height: options.height ?? 2400,
    decodedMimeType: "image/jpeg",
    orientationNormalized: options.orientationNormalized ?? true,
    dispose: vi.fn(),
  };
  const standardized = new Blob(["gray-background"], { type: "image/jpeg" });
  const runtime: BodyPhotoRuntime = {
    decode: vi.fn().mockResolvedValue(decoded),
    measureQuality: vi.fn().mockReturnValue({
      brightnessScore: options.brightness ?? 0.55,
      sharpnessScore: options.sharpness ?? 0.3,
    }),
    normalizeBackground: vi.fn().mockResolvedValue({
      blob: standardized,
      width: 1200,
      height: 2400,
    }),
    createObjectUrl: vi.fn().mockReturnValue("blob:standardized"),
  };
  return {
    processor: new BrowserBodyPhotoProcessor({ detector, segmenter, runtime }),
    detector,
    segmenter,
    runtime,
    decoded,
    standardized,
  };
}

describe("BrowserBodyPhotoProcessor", () => {
  beforeEach(() => vi.restoreAllMocks());

  it.each([
    ["front", "front"],
    ["side", "side"],
    ["back", "front"],
  ] as const)("accepts a valid head-cropped %s portrait", async (view, viewShape) => {
    const { processor, segmenter, runtime, decoded } = setup({ viewShape });

    const result = await processor.process(inputFile(), view);

    expect(result.file.type).toBe("image/jpeg");
    expect(result.previewUrl).toBe("blob:standardized");
    expect(result.validation.visibleLandmarks).toEqual(expect.arrayContaining([
      "shoulders", "arms", "hips", "knees", "ankles", "feet",
    ]));
    expect(segmenter.segment).toHaveBeenCalledWith(decoded);
    expect(runtime.normalizeBackground).toHaveBeenCalledWith(
      decoded,
      expect.objectContaining({ confidence: expect.any(Float32Array) }),
      expect.objectContaining({ background: [160, 163, 161] }),
    );
  });

  it("accepts a front view when wrists are not visible", async () => {
    const { processor } = setup({
      mutate: (value) => {
        value[15]!.visibility = 0.1;
        value[16]!.visibility = 0.1;
      },
    });

    await expect(processor.process(inputFile(), "front")).resolves.toMatchObject({
      validation: { expectedView: "front" },
    });
  });

  it("accepts a side view with hidden far-side landmarks outside the frame", async () => {
    const hiddenFarSide = [12, 14, 16, 24, 26, 28, 32];
    const { processor } = setup({
      viewShape: "side",
      mutate: (value) => {
        for (const index of hiddenFarSide) {
          value[index] = { ...value[index]!, x: 1.1, visibility: 0.1 };
        }
      },
    });

    await expect(processor.process(inputFile(), "side")).resolves.toMatchObject({
      validation: { expectedView: "side" },
    });
  });

  it("accepts a side view when neither elbow is visible", async () => {
    const { processor } = setup({
      viewShape: "side",
      mutate: (value) => {
        value[13]!.visibility = 0.1;
        value[14]!.visibility = 0.1;
      },
    });

    await expect(processor.process(inputFile(), "side")).resolves.toMatchObject({
      validation: { expectedView: "side" },
    });
  });

  it("accepts a back view when each arm has a visible elbow or wrist", async () => {
    const { processor } = setup({
      mutate: (value) => {
        value[15] = { ...value[15]!, x: -0.1, visibility: 0.1 };
        value[14] = { ...value[14]!, x: 1.1, visibility: 0.1 };
      },
    });

    await expect(processor.process(inputFile(), "back")).resolves.toMatchObject({
      validation: { expectedView: "back" },
    });
  });

  it("accepts a back view when one arm is obscured but the body landmarks remain visible", async () => {
    const { processor } = setup({
      mutate: (value) => {
        value[13]!.visibility = 0.1;
        value[15]!.visibility = 0.1;
      },
    });

    await expect(processor.process(inputFile(), "back")).resolves.toMatchObject({
      validation: { expectedView: "back" },
    });
  });

  it("rejects missing shoulders with a specific code", async () => {
    const { processor } = setup({ mutate: (value) => {
      value[11]!.visibility = 0.1;
      value[12]!.visibility = 0.1;
    } });

    await expect(processor.process(inputFile(), "front")).rejects.toMatchObject({
      code: "shoulders_not_visible",
    });
  });

  it("rejects missing legs or feet with a specific code", async () => {
    const { processor } = setup({ mutate: (value) => {
      value[31]!.visibility = 0.1;
      value[32]!.visibility = 0.1;
    } });

    await expect(processor.process(inputFile(), "back")).rejects.toMatchObject({
      code: "legs_or_feet_not_visible",
    });
  });

  it("rejects a material body landmark outside the frame", async () => {
    const { processor } = setup({ mutate: (value) => { value[24]!.x = 1.02; } });

    await expect(processor.process(inputFile(), "front")).rejects.toMatchObject({
      code: "body_out_of_frame",
    });
  });

  it("accepts an essential landmark close to the image edge when it remains inside", async () => {
    const { processor } = setup({ mutate: (value) => { value[24]!.x = 0.003; } });

    await expect(processor.process(inputFile(), "front")).resolves.toMatchObject({
      validation: { expectedView: "front" },
    });
  });

  it("accepts a wide abdomen when the pose and framing landmarks are valid", async () => {
    const wideBodyMask = {
      width: 4,
      height: 4,
      confidence: new Float32Array(16).fill(1),
    };
    const { processor } = setup({ mask: wideBodyMask });

    await expect(processor.process(inputFile(), "front")).resolves.toMatchObject({
      validation: { expectedView: "front" },
    });
  });

  it("accepts small shoulder and hip alignment differences", async () => {
    const { processor } = setup({
      mutate: (value) => {
        value[11]!.x += 0.015;
        value[12]!.x += 0.015;
        value[23]!.x -= 0.01;
        value[24]!.x -= 0.01;
      },
    });

    await expect(processor.process(inputFile(), "front")).resolves.toMatchObject({
      validation: { expectedView: "front" },
    });
  });

  it("rejects two credible spatially distinct people", async () => {
    const primary = landmarks();
    const secondary = translatedPose(landmarks(), 0.3);
    const { processor } = setup({ poses: [primary, secondary] });

    await expect(processor.process(inputFile(), "front")).rejects.toMatchObject({
      code: "multiple_people_detected",
    });
  });

  it("accepts overlapping duplicate detections as one person", async () => {
    const primary = landmarks();
    const duplicate = primary.map((point) => ({ ...point, x: point.x + 0.005 }));
    const { processor } = setup({ poses: [primary, duplicate] });

    await expect(processor.process(inputFile(), "front")).resolves.toBeDefined();
  });

  it("ignores a weak secondary pose candidate", async () => {
    const weak = translatedPose(landmarks(), 0.3).map((point) => ({
      ...point,
      visibility: 0.1,
    }));
    const { processor } = setup({ poses: [landmarks(), weak] });

    await expect(processor.process(inputFile(), "front")).resolves.toBeDefined();
  });

  it.each([
    [0.55, 0.01, "image_too_blurry"],
    [0.05, 0.3, "insufficient_lighting"],
    [0.97, 0.3, "insufficient_lighting"],
  ] as const)("returns an actionable quality error", async (brightness, sharpness, code) => {
    const { processor, segmenter } = setup({ brightness, sharpness });

    await expect(processor.process(inputFile(), "front")).rejects.toMatchObject({ code });
    expect(segmenter.segment).not.toHaveBeenCalled();
  });

  it("accepts a 40 megapixel phone image", async () => {
    const { processor } = setup({ width: 5000, height: 8000 });
    await expect(processor.process(inputFile(), "front")).resolves.toBeDefined();
  });

  it("accepts an EXIF-normalized portrait", async () => {
    const { processor } = setup({ width: 1200, height: 2400, orientationNormalized: true });
    await expect(processor.process(inputFile(), "front")).resolves.toBeDefined();
  });

  it("rejects a clearly side-shaped pose for a requested front view", async () => {
    const { processor } = setup({ viewShape: "side" });
    await expect(processor.process(inputFile(), "front")).rejects.toMatchObject({
      code: "unexpected_body_view",
    });
  });

  it("allows ambiguous front versus back semantics for local guidance", async () => {
    const { processor } = setup({ viewShape: "front" });
    await expect(processor.process(inputFile(), "back")).resolves.toMatchObject({
      validation: { viewAssessment: "ambiguous" },
    });
  });

  it("disposes decoded data even when validation fails", async () => {
    const { processor, decoded } = setup({ poses: [] });
    await expect(processor.process(inputFile(), "front")).rejects.toBeInstanceOf(
      BodyPhotoProcessingError,
    );
    expect(decoded.dispose).toHaveBeenCalledOnce();
  });

  it("passes custom ghostScale and sideProfile options to validator", async () => {
    const { processor } = setup({ viewShape: "side" });
    const result = await processor.process(inputFile(), "side", {
      ghostScale: 0.9,
      sideProfile: "left",
    });

    expect(result.validation.expectedView).toBe("side");
    expect(result.validation.score).toBeGreaterThan(0.7);
  });

  it("includes warnings in validation output for borderline-but-acceptable images", async () => {
    const { processor } = setup({
      mutate: (value) => {
        // borderline foot landmark near edge
        value[31]!.y = 1.001;
      },
    });

    const result = await processor.process(inputFile(), "front");
    expect(result.validation.warnings).toContain("near_boundary_landmarks");
  });
});

describe("compositeBodyOnNeutralBackground", () => {
  it("keeps high-confidence body pixels unchanged and preserves dimensions and alpha", () => {
    const size = 100;
    const source = solidSource(size, size, [20, 30, 40]);
    const result = compositeBodyOnNeutralBackground(
      source,
      size,
      size,
      distanceTestMask(size),
      [160, 163, 161],
    );

    expect(result.length).toBe(source.length);
    expect(pixelAt(result, size, 50, 50)).toEqual([20, 30, 40, 255]);
    expect(Array.from(result).every((value, index) => index % 4 !== 3 || value === 255)).toBe(true);
  });

  it("fades background toward gray as distance from the body increases", () => {
    const size = 100;
    const source = solidSource(size, size, [20, 30, 40]);
    const result = compositeBodyOnNeutralBackground(
      source,
      size,
      size,
      distanceTestMask(size),
      [160, 163, 161],
    );

    const nearBody = pixelAt(result, size, 53, 50);
    const middleDistance = pixelAt(result, size, 56, 50);
    const farBackground = pixelAt(result, size, 70, 50);

    expect(nearBody[0]).toBeLessThan(middleDistance[0]);
    expect(middleDistance[0]).toBeLessThan(farBackground[0]);
    expect(farBackground).toEqual([160, 163, 161, 255]);
  });

  it("reaches neutral gray sooner after the preserved near-body band", () => {
    const size = 100;
    const source = solidSource(size, size, [20, 30, 40]);
    const result = compositeBodyOnNeutralBackground(
      source,
      size,
      size,
      distanceTestMask(size),
      [160, 163, 161],
    );

    const nearBody = pixelAt(result, size, 53, 50);
    const transitionDistance = pixelAt(result, size, 58, 50);
    const mediumDistance = pixelAt(result, size, 60, 50);

    expect(nearBody[0]).toBeLessThan(transitionDistance[0]);
    expect(mediumDistance).toEqual([160, 163, 161, 255]);
  });

  it("fails when the segmentation mask has no valid body seed", () => {
    const size = 4;
    const source = solidSource(size, size, [20, 30, 40]);

    expect(() => compositeBodyOnNeutralBackground(
      source,
      size,
      size,
      { width: size, height: size, confidence: new Float32Array(size * size).fill(0.34) },
      [160, 163, 161],
    )).toThrowError("segmentation_unavailable");
  });
});

function solidSource(width: number, height: number, rgb: readonly [number, number, number]) {
  const source = new Uint8ClampedArray(width * height * 4);
  for (let index = 0; index < source.length; index += 4) {
    source[index] = rgb[0];
    source[index + 1] = rgb[1];
    source[index + 2] = rgb[2];
    source[index + 3] = 255;
  }
  return source;
}

function distanceTestMask(size: number) {
  const confidence = new Float32Array(size * size);
  for (let y = 40; y < 60; y += 1) {
    for (let x = 48; x < 53; x += 1) {
      confidence[y * size + x] = 1;
    }
  }
  return { width: size, height: size, confidence };
}

function pixelAt(source: Uint8ClampedArray, width: number, x: number, y: number) {
  const index = (y * width + x) * 4;
  return [source[index]!, source[index + 1]!, source[index + 2]!, source[index + 3]!];
}
