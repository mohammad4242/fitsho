import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  BrowserBodyPhotoProcessor,
  BodyPhotoProcessingError,
  compositeBodyOnNeutralBackground,
  type BodyLandmarkDetection,
  type BodyLandmarkDetector,
  type BodyPhotoRuntime,
  type BodyPhotoSegmenter,
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

function setup(options: {
  viewShape?: "front" | "side";
  personCount?: number;
  mutate?: (value: NormalizedBodyLandmark[]) => void;
  width?: number;
  height?: number;
  brightness?: number;
  sharpness?: number;
  orientationNormalized?: boolean;
} = {}) {
  const detected = landmarks(options.viewShape);
  options.mutate?.(detected);
  const detection: BodyLandmarkDetection = {
    personCount: options.personCount ?? 1,
    landmarks: detected,
  };
  const detector: BodyLandmarkDetector = { detect: vi.fn().mockResolvedValue(detection) };
  const segmenter: BodyPhotoSegmenter = {
    segment: vi.fn().mockResolvedValue({
      width: 2,
      height: 2,
      confidence: new Float32Array([0, 1, 1, 0]),
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
      expect.objectContaining({ background: [183, 186, 184] }),
    );
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
    const { processor } = setup({ mutate: (value) => { value[16]!.x = 1.02; } });

    await expect(processor.process(inputFile(), "front")).rejects.toMatchObject({
      code: "body_out_of_frame",
    });
  });

  it("reports multiple people from the detector", async () => {
    const { processor } = setup({ personCount: 2 });

    await expect(processor.process(inputFile(), "front")).rejects.toMatchObject({
      code: "multiple_people_detected",
    });
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

  it("allows ambiguous front versus back semantics for AI preflight", async () => {
    const { processor } = setup({ viewShape: "front" });
    await expect(processor.process(inputFile(), "back")).resolves.toMatchObject({
      validation: { viewAssessment: "ambiguous" },
    });
  });

  it("disposes decoded data even when validation fails", async () => {
    const { processor, decoded } = setup({ personCount: 0 });
    await expect(processor.process(inputFile(), "front")).rejects.toBeInstanceOf(
      BodyPhotoProcessingError,
    );
    expect(decoded.dispose).toHaveBeenCalledOnce();
  });
});

describe("compositeBodyOnNeutralBackground", () => {
  it("changes only color values and preserves pixel coordinates", () => {
    const source = new Uint8ClampedArray([
      10, 20, 30, 255,
      100, 110, 120, 255,
    ]);
    const result = compositeBodyOnNeutralBackground(
      source,
      2,
      1,
      { width: 2, height: 1, confidence: new Float32Array([0, 1]) },
      [183, 186, 184],
    );

    expect(Array.from(result)).toEqual([
      183, 186, 184, 255,
      100, 110, 120, 255,
    ]);
  });
});
