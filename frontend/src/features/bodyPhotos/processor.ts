import {
  validatePoseWithGhost,
  type GhostValidationWarning,
} from "./ghostPoseValidator";
import { MediaPipeBodySegmenter } from "./mediaPipeBodySegmenter";
import { MediaPipePoseLandmarkDetector } from "./mediaPipePoseDetector";
import type { BodyPhotoSide, BodyPhotoView } from "./types";

export type NormalizedBodyLandmark = {
  x: number;
  y: number;
  z: number;
  visibility: number;
};

export type BodyLandmarkDetection = {
  poses: NormalizedBodyLandmark[][];
};

export interface BodyLandmarkDetector {
  detect(image: DecodedBodyPhoto): Promise<BodyLandmarkDetection>;
}

export type BodySegmentationMask = {
  width: number;
  height: number;
  confidence: Float32Array;
};

export interface BodyPhotoSegmenter {
  segment(image: DecodedBodyPhoto): Promise<BodySegmentationMask>;
}

export type BodyPhotoQuality = {
  brightnessScore: number;
  sharpnessScore: number;
  minimumLandmarkVisibility: number;
};

export type ProcessBodyPhotoOptions = {
  ghostScale?: number;
  sideProfile?: BodyPhotoSide;
};

export type BodyPhotoValidation = {
  isValid: true;
  expectedView: BodyPhotoView;
  viewAssessment: "matched" | "ambiguous";
  quality: BodyPhotoQuality;
  visibleLandmarks: Array<"shoulders" | "arms" | "hips" | "knees" | "ankles" | "feet">;
  warnings?: GhostValidationWarning[];
  score?: number;
};

export type ProcessedBodyPhoto = {
  file: File;
  previewUrl: string;
  validation: BodyPhotoValidation;
};

export interface BodyPhotoProcessor {
  process(
    file: File,
    view: BodyPhotoView,
    options?: ProcessBodyPhotoOptions,
  ): Promise<ProcessedBodyPhoto>;
}

export type DecodedBodyPhoto = {
  source: CanvasImageSource;
  width: number;
  height: number;
  decodedMimeType: AcceptedImageMimeType;
  orientationNormalized: boolean;
  dispose(): void;
};

export type MeasuredImageQuality = {
  brightnessScore: number;
  sharpnessScore: number;
};

export type BackgroundNormalizationOptions = {
  targetWidth: number;
  quality: number;
  background: readonly [number, number, number];
};

export type EncodedBodyPhoto = {
  blob: Blob;
  width: number;
  height: number;
};

export interface BodyPhotoRuntime {
  decode(file: File): Promise<DecodedBodyPhoto>;
  measureQuality(image: DecodedBodyPhoto): MeasuredImageQuality;
  normalizeBackground(
    image: DecodedBodyPhoto,
    mask: BodySegmentationMask,
    options: BackgroundNormalizationOptions,
  ): Promise<EncodedBodyPhoto>;
  createObjectUrl(blob: Blob): string;
}

type AcceptedImageMimeType = "image/jpeg" | "image/png" | "image/webp";

export type BodyPhotoProcessingErrorCode =
  | "unsupported_format"
  | "invalid_file_size"
  | "image_signature_mismatch"
  | "invalid_image"
  | "invalid_resolution"
  | "image_too_large"
  | "orientation_normalization_failed"
  | "pose_detection_unavailable"
  | "body_not_detected"
  | "multiple_people_detected"
  | "unexpected_body_view"
  | "shoulders_not_visible"
  | "arms_not_visible"
  | "torso_not_visible"
  | "legs_or_feet_not_visible"
  | "body_out_of_frame"
  | "insufficient_lighting"
  | "image_too_blurry"
  | "segmentation_unavailable"
  | "canvas_unavailable"
  | "processing_failed";

export class BodyPhotoProcessingError extends Error {
  readonly code: BodyPhotoProcessingErrorCode;

  constructor(code: BodyPhotoProcessingErrorCode) {
    super(code);
    this.name = "BodyPhotoProcessingError";
    this.code = code;
  }
}

const acceptedMimeTypes = new Set<AcceptedImageMimeType>([
  "image/jpeg",
  "image/png",
  "image/webp",
]);

const limits = {
  maximumFileBytes: 8 * 1024 * 1024,
  minimumWidth: 256,
  minimumHeight: 512,
  maximumPixelCount: 40_000_000,
  minimumBrightnessScore: 0.12,
  maximumBrightnessScore: 0.94,
  minimumSharpnessScore: 0.025,
  minimumLandmarkVisibility: 0.55,
  // Landmark coordinates on the image edge are still usable. Out-of-frame
  // rejection is reserved for coordinates beyond the actual image bounds.
  frameMargin: 0,
  targetWidth: 1200,
  outputQuality: 0.9,
  neutralGray: [160, 163, 161] as const,
} as const;

const bodySeedConfidenceThreshold = 0.35;
const bodyProtectionMinConfidence = 0.20;
const bodyProtectionMaxConfidence = 0.70;
const backgroundFeatherRatio = 0.0675;


export class BrowserBodyPhotoProcessor implements BodyPhotoProcessor {
  private readonly detector: BodyLandmarkDetector;
  private readonly segmenter: BodyPhotoSegmenter;
  private readonly runtime: BodyPhotoRuntime;

  constructor(options: {
    detector?: BodyLandmarkDetector;
    segmenter?: BodyPhotoSegmenter;
    runtime?: BodyPhotoRuntime;
  } = {}) {
    this.detector = options.detector ?? new MediaPipePoseLandmarkDetector();
    this.segmenter = options.segmenter ?? new MediaPipeBodySegmenter();
    this.runtime = options.runtime ?? browserBodyPhotoRuntime;
  }

  async process(
    file: File,
    view: BodyPhotoView,
    options?: ProcessBodyPhotoOptions,
  ): Promise<ProcessedBodyPhoto> {
    if (!acceptedMimeTypes.has(file.type as AcceptedImageMimeType)) {
      throw new BodyPhotoProcessingError("unsupported_format");
    }
    if (file.size === 0 || file.size > limits.maximumFileBytes) {
      throw new BodyPhotoProcessingError("invalid_file_size");
    }

    const image = await this.runtime.decode(file);
    try {
      validateDecodedImage(image, file.type as AcceptedImageMimeType);
      const quality = this.runtime.measureQuality(image);
      validateQuality(quality);
      const detection = await this.detect(image);
      const pose = validateLandmarks(detection, view, options);
      const mask = await this.segment(image);
      const encoded = await this.runtime.normalizeBackground(image, mask, {
        targetWidth: Math.min(limits.targetWidth, image.width),
        quality: limits.outputQuality,
        background: limits.neutralGray,
      });
      if (encoded.blob.size === 0 || encoded.blob.type !== "image/jpeg") {
        throw new BodyPhotoProcessingError("processing_failed");
      }
      const processedFile = new File(
        [encoded.blob],
        `body-photo-${createFileNonce()}.jpg`,
        { type: "image/jpeg", lastModified: Date.now() },
      );
      return {
        file: processedFile,
        previewUrl: this.runtime.createObjectUrl(processedFile),
        validation: {
          isValid: true,
          expectedView: view,
          viewAssessment: pose.viewAssessment,
          quality: {
            brightnessScore: quality.brightnessScore,
            sharpnessScore: quality.sharpnessScore,
            minimumLandmarkVisibility: pose.minimumVisibility,
          },
          visibleLandmarks: pose.visibleLandmarks,
          warnings: pose.warnings,
          score: pose.score,
        },
      };
    } finally {
      image.dispose();
    }
  }

  private async detect(image: DecodedBodyPhoto): Promise<BodyLandmarkDetection> {
    try {
      return await this.detector.detect(image);
    } catch (error) {
      if (error instanceof BodyPhotoProcessingError) throw error;
      throw new BodyPhotoProcessingError("pose_detection_unavailable");
    }
  }

  private async segment(image: DecodedBodyPhoto): Promise<BodySegmentationMask> {
    try {
      const mask = await this.segmenter.segment(image);
      if (
        mask.width <= 0
        || mask.height <= 0
        || mask.confidence.length !== mask.width * mask.height
      ) {
        throw new Error("invalid segmentation mask");
      }
      return mask;
    } catch (error) {
      if (error instanceof BodyPhotoProcessingError) throw error;
      throw new BodyPhotoProcessingError("segmentation_unavailable");
    }
  }
}

type ValidatedPose = {
  viewAssessment: "matched" | "ambiguous";
  minimumVisibility: number;
  visibleLandmarks: BodyPhotoValidation["visibleLandmarks"];
  warnings: GhostValidationWarning[];
  score: number;
};

function validateLandmarks(
  detection: BodyLandmarkDetection,
  expectedView: BodyPhotoView,
  options?: ProcessBodyPhotoOptions,
): ValidatedPose {
  const result = validatePoseWithGhost({
    view: expectedView,
    sideProfile: options?.sideProfile,
    ghostScale: options?.ghostScale,
    poses: detection.poses,
  });

  if (result.status === "fail" && result.hardRejectCode) {
    throw new BodyPhotoProcessingError(result.hardRejectCode);
  }

  return {
    viewAssessment: result.viewAssessment,
    minimumVisibility: result.minimumVisibility,
    visibleLandmarks: result.visibleLandmarks,
    warnings: result.warnings,
    score: result.overallScore,
  };
}

function validateDecodedImage(image: DecodedBodyPhoto, declaredMimeType: AcceptedImageMimeType) {
  if (image.decodedMimeType !== declaredMimeType) {
    throw new BodyPhotoProcessingError("image_signature_mismatch");
  }
  if (!image.orientationNormalized) {
    throw new BodyPhotoProcessingError("orientation_normalization_failed");
  }
  if (
    image.width < limits.minimumWidth
    || image.height < limits.minimumHeight
    || image.height < image.width
    || image.height > image.width * 3
  ) {
    throw new BodyPhotoProcessingError("invalid_resolution");
  }
  if (image.width * image.height > limits.maximumPixelCount) {
    throw new BodyPhotoProcessingError("image_too_large");
  }
}

function validateQuality(quality: MeasuredImageQuality) {
  if (
    quality.brightnessScore < limits.minimumBrightnessScore
    || quality.brightnessScore > limits.maximumBrightnessScore
  ) {
    throw new BodyPhotoProcessingError("insufficient_lighting");
  }
  if (quality.sharpnessScore < limits.minimumSharpnessScore) {
    throw new BodyPhotoProcessingError("image_too_blurry");
  }
}

export class BrowserBodyPhotoRuntime implements BodyPhotoRuntime {
  async decode(file: File): Promise<DecodedBodyPhoto> {
    const declaredMimeType = file.type as AcceptedImageMimeType;
    const signatureBytes = new Uint8Array(await file.slice(0, 16).arrayBuffer());
    const decodedMimeType = sniffMimeType(signatureBytes);
    if (decodedMimeType === null || decodedMimeType !== declaredMimeType) {
      throw new BodyPhotoProcessingError("image_signature_mismatch");
    }
    if (typeof createImageBitmap === "function") {
      try {
        const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
        return {
          source: bitmap,
          width: bitmap.width,
          height: bitmap.height,
          decodedMimeType,
          orientationNormalized: true,
          dispose: () => bitmap.close(),
        };
      } catch {
        throw new BodyPhotoProcessingError("invalid_image");
      }
    }
    return decodeWithImageElement(file, decodedMimeType);
  }

  measureQuality(image: DecodedBodyPhoto): MeasuredImageQuality {
    const maximumSampleEdge = 320;
    const scale = Math.min(1, maximumSampleEdge / Math.max(image.width, image.height));
    const width = Math.max(1, Math.round(image.width * scale));
    const height = Math.max(1, Math.round(image.height * scale));
    const canvas = createCanvas(width, height);
    const context = requireContext(canvas);
    context.drawImage(image.source, 0, 0, width, height);
    const pixels = context.getImageData(0, 0, width, height).data;
    if (pixels.length === 0) throw new BodyPhotoProcessingError("invalid_image");

    let brightnessTotal = 0;
    let edgeTotal = 0;
    let edgeSamples = 0;
    let previousLuma: number | null = null;
    for (let index = 0; index < pixels.length; index += 4) {
      const luma = (pixels[index]! * 0.2126)
        + (pixels[index + 1]! * 0.7152)
        + (pixels[index + 2]! * 0.0722);
      brightnessTotal += luma;
      if (previousLuma !== null && (index / 4) % width !== 0) {
        edgeTotal += Math.abs(luma - previousLuma);
        edgeSamples += 1;
      }
      previousLuma = luma;
    }
    const pixelCount = pixels.length / 4;
    return {
      brightnessScore: clampScore(brightnessTotal / pixelCount / 255),
      sharpnessScore: clampScore(edgeSamples === 0 ? 0 : edgeTotal / edgeSamples / 64),
    };
  }

  async normalizeBackground(
    image: DecodedBodyPhoto,
    mask: BodySegmentationMask,
    options: BackgroundNormalizationOptions,
  ): Promise<EncodedBodyPhoto> {
    const outputWidth = Math.min(options.targetWidth, image.width);
    const outputHeight = Math.max(1, Math.round((image.height / image.width) * outputWidth));
    const canvas = createCanvas(outputWidth, outputHeight);
    const context = requireContext(canvas);
    context.drawImage(image.source, 0, 0, outputWidth, outputHeight);
    const imageData = context.getImageData(0, 0, outputWidth, outputHeight);
    imageData.data.set(compositeBodyOnNeutralBackground(
      imageData.data,
      outputWidth,
      outputHeight,
      mask,
      options.background,
    ));
    context.putImageData(imageData, 0, 0);
    return {
      blob: await canvasToBlob(canvas, options.quality),
      width: outputWidth,
      height: outputHeight,
    };
  }

  createObjectUrl(blob: Blob): string {
    return URL.createObjectURL(blob);
  }
}

export function compositeBodyOnNeutralBackground(
  source: Uint8ClampedArray,
  width: number,
  height: number,
  mask: BodySegmentationMask,
  background: readonly [number, number, number],
): Uint8ClampedArray {
  if (
    width <= 0
    || height <= 0
    || mask.width <= 0
    || mask.height <= 0
    || source.length !== width * height * 4
    || mask.confidence.length !== mask.width * mask.height
  ) {
    throw new BodyPhotoProcessingError("segmentation_unavailable");
  }
  const distanceField = buildBodyDistanceField(mask, width, height);
  const featherRadius = Math.max(1, Math.min(width, height) * backgroundFeatherRatio);
  const output = new Uint8ClampedArray(source.length);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const confidence = clampConfidence(sampleMaskValue(
        mask.confidence,
        mask.width,
        mask.height,
        width,
        height,
        x,
        y,
      ));
      const distanceFromBody = sampleMaskValue(
        distanceField,
        mask.width,
        mask.height,
        width,
        height,
        x,
        y,
      );
      const bodyProtection = smoothstep(
        bodyProtectionMinConfidence,
        bodyProtectionMaxConfidence,
        confidence,
      );
      const distanceFade = smoothstep(0, featherRadius, distanceFromBody);
      const grayMix = (1 - bodyProtection) * distanceFade;
      const index = (y * width + x) * 4;
      output[index] = Math.round(source[index]! * (1 - grayMix) + background[0] * grayMix);
      output[index + 1] = Math.round(source[index + 1]! * (1 - grayMix) + background[1] * grayMix);
      output[index + 2] = Math.round(source[index + 2]! * (1 - grayMix) + background[2] * grayMix);
      output[index + 3] = 255;
    }
  }
  return output;
}

function buildBodyDistanceField(
  mask: BodySegmentationMask,
  outputWidth: number,
  outputHeight: number,
): Float32Array {
  const distances = new Float32Array(mask.width * mask.height);
  distances.fill(Number.POSITIVE_INFINITY);
  let hasBodySeed = false;
  for (let y = 0; y < mask.height; y += 1) {
    for (let x = 0; x < mask.width; x += 1) {
      const index = y * mask.width + x;
      if (clampConfidence(mask.confidence[index]!) >= bodySeedConfidenceThreshold) {
        distances[index] = 0;
        hasBodySeed = true;
      }
    }
  }
  if (!hasBodySeed) throw new BodyPhotoProcessingError("segmentation_unavailable");

  const horizontalStep = outputWidth / mask.width;
  const verticalStep = outputHeight / mask.height;
  const diagonalStep = Math.hypot(horizontalStep, verticalStep);
  for (let y = 0; y < mask.height; y += 1) {
    for (let x = 0; x < mask.width; x += 1) {
      const index = y * mask.width + x;
      let distance = distances[index]!;
      if (x > 0) distance = Math.min(distance, distances[index - 1]! + horizontalStep);
      if (y > 0) distance = Math.min(distance, distances[index - mask.width]! + verticalStep);
      if (x > 0 && y > 0) {
        distance = Math.min(distance, distances[index - mask.width - 1]! + diagonalStep);
      }
      if (x + 1 < mask.width && y > 0) {
        distance = Math.min(distance, distances[index - mask.width + 1]! + diagonalStep);
      }
      distances[index] = distance;
    }
  }
  for (let y = mask.height - 1; y >= 0; y -= 1) {
    for (let x = mask.width - 1; x >= 0; x -= 1) {
      const index = y * mask.width + x;
      let distance = distances[index]!;
      if (x + 1 < mask.width) distance = Math.min(distance, distances[index + 1]! + horizontalStep);
      if (y + 1 < mask.height) distance = Math.min(distance, distances[index + mask.width]! + verticalStep);
      if (x + 1 < mask.width && y + 1 < mask.height) {
        distance = Math.min(distance, distances[index + mask.width + 1]! + diagonalStep);
      }
      if (x > 0 && y + 1 < mask.height) {
        distance = Math.min(distance, distances[index + mask.width - 1]! + diagonalStep);
      }
      distances[index] = distance;
    }
  }
  return distances;
}

function sampleMaskValue(
  values: Float32Array,
  maskWidth: number,
  maskHeight: number,
  outputWidth: number,
  outputHeight: number,
  x: number,
  y: number,
): number {
  const mappedX = Math.min(maskWidth - 1, Math.max(0, ((x + 0.5) / outputWidth) * maskWidth - 0.5));
  const mappedY = Math.min(maskHeight - 1, Math.max(0, ((y + 0.5) / outputHeight) * maskHeight - 0.5));
  const left = Math.floor(mappedX);
  const top = Math.floor(mappedY);
  const right = Math.min(maskWidth - 1, left + 1);
  const bottom = Math.min(maskHeight - 1, top + 1);
  const xWeight = mappedX - left;
  const yWeight = mappedY - top;
  const topLeft = values[top * maskWidth + left]!;
  const topRight = values[top * maskWidth + right]!;
  const bottomLeft = values[bottom * maskWidth + left]!;
  const bottomRight = values[bottom * maskWidth + right]!;
  const topValue = topLeft + (topRight - topLeft) * xWeight;
  const bottomValue = bottomLeft + (bottomRight - bottomLeft) * xWeight;
  return topValue + (bottomValue - topValue) * yWeight;
}

function smoothstep(edgeStart: number, edgeEnd: number, value: number): number {
  const normalized = Math.min(1, Math.max(0, (value - edgeStart) / (edgeEnd - edgeStart)));
  return normalized * normalized * (3 - 2 * normalized);
}

function clampConfidence(value: number): number {
  return Number.isFinite(value) ? Math.min(1, Math.max(0, value)) : 0;
}

const browserBodyPhotoRuntime = new BrowserBodyPhotoRuntime();
export const browserBodyPhotoProcessor = new BrowserBodyPhotoProcessor();

function decodeWithImageElement(
  file: File,
  decodedMimeType: AcceptedImageMimeType,
): Promise<DecodedBodyPhoto> {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file);
    const image = new Image();
    const release = () => URL.revokeObjectURL(objectUrl);
    image.onload = () => {
      release();
      if (image.naturalWidth === 0 || image.naturalHeight === 0) {
        reject(new BodyPhotoProcessingError("invalid_image"));
        return;
      }
      resolve({
        source: image,
        width: image.naturalWidth,
        height: image.naturalHeight,
        decodedMimeType,
        orientationNormalized: true,
        dispose: () => { image.src = ""; },
      });
    };
    image.onerror = () => {
      release();
      reject(new BodyPhotoProcessingError("invalid_image"));
    };
    image.src = objectUrl;
  });
}

function sniffMimeType(bytes: Uint8Array): AcceptedImageMimeType | null {
  if (bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) {
    return "image/jpeg";
  }
  if (
    bytes.length >= 8
    && bytes[0] === 0x89
    && bytes[1] === 0x50
    && bytes[2] === 0x4e
    && bytes[3] === 0x47
    && bytes[4] === 0x0d
    && bytes[5] === 0x0a
    && bytes[6] === 0x1a
    && bytes[7] === 0x0a
  ) return "image/png";
  if (
    bytes.length >= 12
    && String.fromCharCode(...bytes.slice(0, 4)) === "RIFF"
    && String.fromCharCode(...bytes.slice(8, 12)) === "WEBP"
  ) return "image/webp";
  return null;
}

function createCanvas(width: number, height: number): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  return canvas;
}

function requireContext(canvas: HTMLCanvasElement): CanvasRenderingContext2D {
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (context === null) throw new BodyPhotoProcessingError("canvas_unavailable");
  return context;
}

function canvasToBlob(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob === null) reject(new BodyPhotoProcessingError("processing_failed"));
      else resolve(blob);
    }, "image/jpeg", quality);
  });
}

function clampScore(value: number): number {
  return Math.min(1, Math.max(0, Number(value.toFixed(4))));
}

function createFileNonce(): string {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID() : String(Date.now());
}
