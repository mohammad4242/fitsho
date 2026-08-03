import { afterEach, describe, expect, it, vi } from "vitest";

import type { BodyPhotoView } from "./types";
import {
  BrowserBodyPhotoProcessor,
  BrowserBodyPhotoRuntime,
  BodyPhotoProcessingError,
  type BodyLandmarkDetection,
  type BodyLandmarkDetector,
  type BodyPhotoRuntime,
  type DecodedBodyPhoto,
} from "./processor";

const jpegBytes = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10]).buffer as ArrayBuffer;

function inputFile(type = "image/jpeg", bytes: ArrayBuffer = jpegBytes) {
  return new File([bytes], "body.jpg", { type });
}

function validDetection(view: BodyPhotoView): BodyLandmarkDetection {
  return {
    personCount: 1,
    detectedView: view,
    detectionConfidence: 0.96,
    poseScore: 0.92,
    bodyCompletenessScore: 0.94,
    clothingVisibilityScore: 0.9,
    backgroundReliabilityScore: 0.88,
    isSafeAndRelevant: true,
    safeHeadCropY: 0.18,
    shoulderLineY: 0.25,
    headFullyExcluded: true,
    shouldersPreserved: true,
    headCropConfidence: 0.95,
    warnings: [],
  };
}

function makeRuntime() {
  const dispose = vi.fn();
  const decoded: DecodedBodyPhoto = {
    source: {} as CanvasImageSource,
    width: 1200,
    height: 1800,
    decodedMimeType: "image/jpeg",
    orientationNormalized: true,
    dispose,
  };
  const output = new Blob(["head-cropped-output"], { type: "image/jpeg" });
  const runtime: BodyPhotoRuntime = {
    decode: vi.fn().mockResolvedValue(decoded),
    measureQuality: vi.fn().mockReturnValue({ brightnessScore: 0.78, sharpnessScore: 0.84 }),
    cropAndEncode: vi.fn().mockResolvedValue(output),
    createObjectUrl: vi.fn().mockReturnValue("blob:anonymized-preview"),
    sha256: vi.fn()
      .mockResolvedValueOnce("a".repeat(64))
      .mockResolvedValueOnce("b".repeat(64)),
  };
  return { runtime, decoded, dispose, output };
}

function detector(result: BodyLandmarkDetection): BodyLandmarkDetector {
  return { detect: vi.fn().mockResolvedValue(result) };
}

afterEach(() => vi.restoreAllMocks());

describe("BrowserBodyPhotoProcessor", () => {
  it("returns only a newly encoded head-cropped file and structured validation metadata", async () => {
    const { runtime, output, dispose } = makeRuntime();
    const original = inputFile();
    const result = await new BrowserBodyPhotoProcessor({
      detector: detector(validDetection("front")),
      runtime,
    }).process(original, "front");

    expect(result.file).not.toBe(original);
    expect(await result.file.text()).toBe(await output.text());
    expect(result.previewUrl).toBe("blob:anonymized-preview");
    expect(result.validation).toMatchObject({
      isValid: true,
      expectedView: "front",
      detectedView: "front",
      quality: {
        brightnessScore: 0.78,
        sharpnessScore: 0.84,
        poseScore: 0.92,
        bodyCompletenessScore: 0.94,
        clothingVisibilityScore: 0.9,
      },
      crop: { headRemoved: true, confidence: 0.95 },
    });
    expect(runtime.cropAndEncode).toHaveBeenCalledWith(expect.anything(), {
      top: 324,
      bottom: 1800,
      targetWidth: 1200,
      quality: 0.9,
    });
    expect(dispose).toHaveBeenCalledOnce();
  });

  it("fails closed when no detector is configured", async () => {
    const { runtime, dispose } = makeRuntime();
    await expect(new BrowserBodyPhotoProcessor({ runtime }).process(inputFile(), "front"))
      .rejects.toMatchObject({ code: "pose_detection_unavailable" });
    expect(dispose).toHaveBeenCalledOnce();
  });

  it.each([
    ["multiple people", { personCount: 2 }, "exactly_one_person_required"],
    ["wrong view", { detectedView: "side" }, "unexpected_body_view"],
    ["hidden body", { bodyCompletenessScore: 0.4 }, "body_not_fully_visible"],
    ["unsuitable clothing", { clothingVisibilityScore: 0.3 }, "clothing_hides_body_contours"],
    ["unsafe content", { isSafeAndRelevant: false }, "unsafe_or_irrelevant_image"],
    ["unreliable background", { backgroundReliabilityScore: 0.2 }, "body_not_fully_visible"],
    ["unsafe crop", { headFullyExcluded: false }, "safe_head_crop_unavailable"],
    ["shoulders removed", { shouldersPreserved: false }, "safe_head_crop_unavailable"],
    ["crop below shoulders", { safeHeadCropY: 0.3 }, "safe_head_crop_unavailable"],
  ])("rejects %s and releases decoded image resources", async (_label, override, code) => {
    const { runtime, dispose } = makeRuntime();
    const detection = { ...validDetection("front"), ...override } as BodyLandmarkDetection;
    await expect(new BrowserBodyPhotoProcessor({
      detector: detector(detection),
      runtime,
    }).process(inputFile(), "front")).rejects.toMatchObject({ code });
    expect(runtime.cropAndEncode).not.toHaveBeenCalled();
    expect(dispose).toHaveBeenCalledOnce();
  });

  it("rejects blurry or badly lit images before encoding", async () => {
    const { runtime, dispose } = makeRuntime();
    vi.mocked(runtime.measureQuality).mockReturnValue({ brightnessScore: 0.06, sharpnessScore: 0.02 });
    await expect(new BrowserBodyPhotoProcessor({
      detector: detector(validDetection("back")),
      runtime,
    }).process(inputFile(), "back")).rejects.toBeInstanceOf(BodyPhotoProcessingError);
    expect(runtime.cropAndEncode).not.toHaveBeenCalled();
    expect(dispose).toHaveBeenCalledOnce();
  });

  it("rejects MIME/signature mismatch before body detection", async () => {
    const { runtime } = makeRuntime();
    vi.mocked(runtime.decode).mockRejectedValue(
      new BodyPhotoProcessingError("image_signature_mismatch"),
    );
    await expect(new BrowserBodyPhotoProcessor({
      detector: detector(validDetection("front")),
      runtime,
    }).process(inputFile("image/png"), "front")).rejects.toMatchObject({
      code: "image_signature_mismatch",
    });
  });

  it("checks the decoded file signature instead of trusting the declared MIME type", async () => {
    const pngSignature = new Uint8Array([
      0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
    ]).buffer as ArrayBuffer;
    await expect(
      new BrowserBodyPhotoRuntime().decode(inputFile("image/jpeg", pngSignature)),
    ).rejects.toMatchObject({ code: "image_signature_mismatch" });
  });

  it("rejects a decoder that did not normalize image orientation", async () => {
    const { runtime, decoded, dispose } = makeRuntime();
    decoded.orientationNormalized = false;
    await expect(new BrowserBodyPhotoProcessor({
      detector: detector(validDetection("front")),
      runtime,
    }).process(inputFile(), "front")).rejects.toMatchObject({
      code: "orientation_normalization_failed",
    });
    expect(dispose).toHaveBeenCalledOnce();
  });
});
