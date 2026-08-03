import type { BodyPhotoView } from "./types";
import { MediaPipePoseLandmarkDetector } from "./mediaPipePoseDetector";

export type BodyPhotoQuality = {
  overallScore: number;
  brightnessScore: number;
  sharpnessScore: number;
  poseScore: number;
  bodyCompletenessScore: number;
  clothingVisibilityScore: number;
  backgroundReliabilityScore: number;
};

export type BodyPhotoValidation = {
  isValid: true;
  expectedView: BodyPhotoView;
  detectedView: BodyPhotoView;
  quality: BodyPhotoQuality;
  warnings: string[];
  crop: {
    headRemoved: true;
    confidence: number;
  };
};

export type ProcessedBodyPhoto = {
  file: File;
  previewUrl: string;
  originalHeight: number;
  cropTop: number;
  cropBottom: number;
  cropConfidence: number;
  processedSha256: string;
  cropEvidenceSha256: string;
  validation: BodyPhotoValidation;
};

export interface BodyPhotoProcessor {
  process(file: File, view: BodyPhotoView): Promise<ProcessedBodyPhoto>;
}

export type BodyLandmarkDetection = {
  personCount: number;
  detectedView: BodyPhotoView | "unknown";
  detectionConfidence: number;
  poseScore: number;
  bodyCompletenessScore: number;
  clothingVisibilityScore: number;
  backgroundReliabilityScore: number;
  isSafeAndRelevant: boolean;
  clothingValidation: "accepted" | "rejected" | "unavailable";
  contentSafetyValidation: "accepted" | "rejected" | "unavailable";
  backgroundValidation: "accepted" | "rejected" | "unavailable";
  /** Lowest confidently observed face/head landmark in normalized image coordinates. */
  faceBottomY: number | null;
  /** Normalized Y coordinate below the complete head and above both shoulders. */
  safeHeadCropY: number | null;
  /** Normalized Y coordinate of the highest shoulder landmark. */
  shoulderLineY: number | null;
  headFullyExcluded: boolean;
  shouldersPreserved: boolean;
  headCropConfidence: number;
  warnings: string[];
};

export interface BodyLandmarkDetector {
  detect(image: DecodedBodyPhoto, expectedView: BodyPhotoView): Promise<BodyLandmarkDetection>;
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

export type CropRequest = {
  top: number;
  bottom: number;
  targetWidth: number;
  quality: number;
};

export type EncodedCrop = {
  blob: Blob;
  width: number;
  height: number;
};

export interface BodyPhotoRuntime {
  decode(file: File): Promise<DecodedBodyPhoto>;
  measureQuality(image: DecodedBodyPhoto): MeasuredImageQuality;
  cropAndEncode(image: DecodedBodyPhoto, crop: CropRequest): Promise<EncodedCrop>;
  createObjectUrl(blob: Blob): string;
  sha256(value: ArrayBuffer): Promise<string>;
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
  | "exactly_one_person_required"
  | "unexpected_body_view"
  | "low_pose_confidence"
  | "body_not_fully_visible"
  | "clothing_hides_body_contours"
  | "clothing_validation_unavailable"
  | "content_validation_unavailable"
  | "background_validation_unavailable"
  | "unsafe_or_irrelevant_image"
  | "image_too_dark"
  | "image_too_bright"
  | "image_too_blurry"
  | "safe_head_crop_unavailable"
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

const defaultLimits = {
  maximumFileBytes: 8 * 1024 * 1024,
  minimumWidth: 256,
  minimumHeight: 512,
  maximumPixelCount: 40_000_000,
  minimumDetectionConfidence: 0.7,
  minimumPoseScore: 0.7,
  minimumBodyCompletenessScore: 0.82,
  minimumClothingVisibilityScore: 0.65,
  minimumCropConfidence: 0.8,
  minimumBrightnessScore: 0.12,
  maximumBrightnessScore: 0.94,
  minimumSharpnessScore: 0.025,
  targetWidth: 1200,
  outputQuality: 0.9,
  minimumFaceCropSafetyMargin: 0.04,
} as const;

export class BrowserBodyPhotoProcessor implements BodyPhotoProcessor {
  private readonly detector: BodyLandmarkDetector;
  private readonly runtime: BodyPhotoRuntime;

  constructor(options: {
    detector?: BodyLandmarkDetector;
    runtime?: BodyPhotoRuntime;
  } = {}) {
    this.detector = options.detector ?? new MediaPipePoseLandmarkDetector();
    this.runtime = options.runtime ?? browserBodyPhotoRuntime;
  }

  async process(file: File, view: BodyPhotoView): Promise<ProcessedBodyPhoto> {
    if (!acceptedMimeTypes.has(file.type as AcceptedImageMimeType)) {
      throw new BodyPhotoProcessingError("unsupported_format");
    }
    if (file.size === 0 || file.size > defaultLimits.maximumFileBytes) {
      throw new BodyPhotoProcessingError("invalid_file_size");
    }

    const image = await this.runtime.decode(file);
    try {
      this.validateDecodedImage(image, file.type as AcceptedImageMimeType);
      const detection = await this.detectBody(image, view);
      this.validateDetection(detection, view);
      const measuredQuality = this.runtime.measureQuality(image);
      this.validateMeasuredQuality(measuredQuality);

      const safeCropY = detection.safeHeadCropY;
      if (safeCropY === null) {
        throw new BodyPhotoProcessingError("safe_head_crop_unavailable");
      }
      const cropTop = Math.ceil(image.height * safeCropY);
      const cropBottom = image.height;
      const encodedCrop = await this.runtime.cropAndEncode(image, {
        top: cropTop,
        bottom: cropBottom,
        targetWidth: Math.min(defaultLimits.targetWidth, image.width),
        quality: defaultLimits.outputQuality,
      });
      if (encodedCrop.blob.size === 0 || encodedCrop.blob.type !== "image/jpeg") {
        throw new BodyPhotoProcessingError("processing_failed");
      }

      const processedBytes = await encodedCrop.blob.arrayBuffer();
      const processedSha256 = await this.runtime.sha256(processedBytes);
      // The backend verifies crop geometry against the resized output. Preserve the
      // source crop ratio in a scaled coordinate system whose crop height exactly
      // matches the encoded image height.
      const scaledCropTop = Math.max(
        1,
        Math.round((cropTop / (cropBottom - cropTop)) * encodedCrop.height),
      );
      const evidenceOriginalHeight = scaledCropTop + encodedCrop.height;
      const evidenceCropBottom = evidenceOriginalHeight;
      const cropEvidenceSha256 = await this.runtime.sha256(
        new TextEncoder().encode(
          `v1:${processedSha256}:${evidenceOriginalHeight}:${scaledCropTop}:${evidenceCropBottom}`,
        ).buffer,
      );
      const processedFile = new File(
        [encodedCrop.blob],
        `body-photo-${createFileNonce()}.jpg`,
        { type: "image/jpeg", lastModified: Date.now() },
      );
      const quality = buildQuality(measuredQuality, detection);

      return {
        file: processedFile,
        previewUrl: this.runtime.createObjectUrl(processedFile),
        originalHeight: evidenceOriginalHeight,
        cropTop: scaledCropTop,
        cropBottom: evidenceCropBottom,
        cropConfidence: detection.headCropConfidence,
        processedSha256,
        cropEvidenceSha256,
        validation: {
          isValid: true,
          expectedView: view,
          detectedView: detection.detectedView as BodyPhotoView,
          quality,
          warnings: detection.warnings,
          crop: {
            headRemoved: true,
            confidence: detection.headCropConfidence,
          },
        },
      };
    } finally {
      image.dispose();
    }
  }

  private async detectBody(image: DecodedBodyPhoto, view: BodyPhotoView) {
    try {
      return await this.detector.detect(image, view);
    } catch (error) {
      if (error instanceof BodyPhotoProcessingError) throw error;
      throw new BodyPhotoProcessingError("pose_detection_unavailable");
    }
  }

  private validateDecodedImage(image: DecodedBodyPhoto, declaredMimeType: AcceptedImageMimeType) {
    if (image.decodedMimeType !== declaredMimeType) {
      throw new BodyPhotoProcessingError("image_signature_mismatch");
    }
    if (!image.orientationNormalized) {
      throw new BodyPhotoProcessingError("orientation_normalization_failed");
    }
    if (image.width < defaultLimits.minimumWidth || image.height < defaultLimits.minimumHeight) {
      throw new BodyPhotoProcessingError("invalid_resolution");
    }
    if (image.width * image.height > defaultLimits.maximumPixelCount) {
      throw new BodyPhotoProcessingError("image_too_large");
    }
  }

  private validateDetection(detection: BodyLandmarkDetection, expectedView: BodyPhotoView) {
    if (detection.personCount !== 1) {
      throw new BodyPhotoProcessingError("exactly_one_person_required");
    }
    if (detection.clothingValidation === "unavailable") {
      throw new BodyPhotoProcessingError("clothing_validation_unavailable");
    }
    if (detection.contentSafetyValidation === "unavailable") {
      throw new BodyPhotoProcessingError("content_validation_unavailable");
    }
    if (detection.backgroundValidation === "unavailable") {
      throw new BodyPhotoProcessingError("background_validation_unavailable");
    }
    if (detection.clothingValidation === "rejected") {
      throw new BodyPhotoProcessingError("clothing_hides_body_contours");
    }
    if (!detection.isSafeAndRelevant) {
      throw new BodyPhotoProcessingError("unsafe_or_irrelevant_image");
    }
    if (detection.detectedView !== expectedView) {
      throw new BodyPhotoProcessingError("unexpected_body_view");
    }
    if (
      detection.detectionConfidence < defaultLimits.minimumDetectionConfidence
      || detection.poseScore < defaultLimits.minimumPoseScore
    ) {
      throw new BodyPhotoProcessingError("low_pose_confidence");
    }
    if (detection.bodyCompletenessScore < defaultLimits.minimumBodyCompletenessScore) {
      throw new BodyPhotoProcessingError("body_not_fully_visible");
    }
    if (detection.clothingVisibilityScore < defaultLimits.minimumClothingVisibilityScore) {
      throw new BodyPhotoProcessingError("clothing_hides_body_contours");
    }
    if (detection.backgroundReliabilityScore < 0.5) {
      throw new BodyPhotoProcessingError("body_not_fully_visible");
    }
    if (
      detection.safeHeadCropY === null
      || detection.shoulderLineY === null
      || detection.faceBottomY === null
      || !detection.headFullyExcluded
      || !detection.shouldersPreserved
      || detection.headCropConfidence < defaultLimits.minimumCropConfidence
      || detection.safeHeadCropY <= 0
      || detection.safeHeadCropY >= detection.shoulderLineY
      || detection.safeHeadCropY
        < detection.faceBottomY + defaultLimits.minimumFaceCropSafetyMargin
      || detection.shoulderLineY - detection.safeHeadCropY > 0.18
      || detection.shoulderLineY >= 0.5
    ) {
      throw new BodyPhotoProcessingError("safe_head_crop_unavailable");
    }
  }

  private validateMeasuredQuality(quality: MeasuredImageQuality) {
    if (quality.brightnessScore < defaultLimits.minimumBrightnessScore) {
      throw new BodyPhotoProcessingError("image_too_dark");
    }
    if (quality.brightnessScore > defaultLimits.maximumBrightnessScore) {
      throw new BodyPhotoProcessingError("image_too_bright");
    }
    if (quality.sharpnessScore < defaultLimits.minimumSharpnessScore) {
      throw new BodyPhotoProcessingError("image_too_blurry");
    }
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
    if (pixels.length === 0) {
      throw new BodyPhotoProcessingError("invalid_image");
    }

    let brightnessTotal = 0;
    let edgeTotal = 0;
    let edgeSamples = 0;
    let previousLuma: number | null = null;
    for (let index = 0; index < pixels.length; index += 4) {
      const luma = (pixels[index] * 0.2126) + (pixels[index + 1] * 0.7152) + (pixels[index + 2] * 0.0722);
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

  async cropAndEncode(image: DecodedBodyPhoto, crop: CropRequest): Promise<EncodedCrop> {
    const cropHeight = crop.bottom - crop.top;
    if (crop.top < 0 || cropHeight <= 0 || crop.bottom > image.height) {
      throw new BodyPhotoProcessingError("safe_head_crop_unavailable");
    }
    const outputWidth = Math.min(crop.targetWidth, image.width);
    const outputHeight = Math.max(1, Math.round((cropHeight / image.width) * outputWidth));
    const canvas = createCanvas(outputWidth, outputHeight);
    const context = requireContext(canvas);
    context.drawImage(
      image.source,
      0,
      crop.top,
      image.width,
      cropHeight,
      0,
      0,
      outputWidth,
      outputHeight,
    );
    return {
      blob: await canvasToBlob(canvas, crop.quality),
      width: outputWidth,
      height: outputHeight,
    };
  }

  createObjectUrl(blob: Blob): string {
    return URL.createObjectURL(blob);
  }

  async sha256(value: ArrayBuffer): Promise<string> {
    const digest = await crypto.subtle.digest("SHA-256", value);
    return Array.from(
      new Uint8Array(digest),
      (byte) => byte.toString(16).padStart(2, "0"),
    ).join("");
  }
}

const browserBodyPhotoRuntime = new BrowserBodyPhotoRuntime();

/**
 * The default processor uses an on-device MediaPipe landmarker. If its model or
 * runtime cannot load, processing fails closed and no selected image is uploaded.
 */
export const browserBodyPhotoProcessor = new BrowserBodyPhotoProcessor();

function decodeWithImageElement(
  file: File,
  decodedMimeType: AcceptedImageMimeType,
): Promise<DecodedBodyPhoto> {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file);
    const image = new Image();
    const releaseObjectUrl = () => URL.revokeObjectURL(objectUrl);
    image.onload = () => {
      releaseObjectUrl();
      if (image.naturalWidth === 0 || image.naturalHeight === 0) {
        image.src = "";
        reject(new BodyPhotoProcessingError("invalid_image"));
        return;
      }
      resolve({
        source: image,
        width: image.naturalWidth,
        height: image.naturalHeight,
        decodedMimeType,
        orientationNormalized: true,
        dispose: () => {
          image.onload = null;
          image.onerror = null;
          image.src = "";
        },
      });
    };
    image.onerror = () => {
      releaseObjectUrl();
      image.src = "";
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
  ) {
    return "image/png";
  }
  if (
    bytes.length >= 12
    && String.fromCharCode(...bytes.slice(0, 4)) === "RIFF"
    && String.fromCharCode(...bytes.slice(8, 12)) === "WEBP"
  ) {
    return "image/webp";
  }
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
  if (context === null) {
    throw new BodyPhotoProcessingError("canvas_unavailable");
  }
  return context;
}

function canvasToBlob(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob === null) {
        reject(new BodyPhotoProcessingError("processing_failed"));
        return;
      }
      resolve(blob);
    }, "image/jpeg", quality);
  });
}

function buildQuality(
  measured: MeasuredImageQuality,
  detection: BodyLandmarkDetection,
): BodyPhotoQuality {
  const scores = [
    measured.brightnessScore,
    measured.sharpnessScore,
    detection.poseScore,
    detection.bodyCompletenessScore,
    detection.clothingVisibilityScore,
    detection.backgroundReliabilityScore,
  ];
  return {
    overallScore: clampScore(scores.reduce((total, score) => total + score, 0) / scores.length),
    brightnessScore: measured.brightnessScore,
    sharpnessScore: measured.sharpnessScore,
    poseScore: detection.poseScore,
    bodyCompletenessScore: detection.bodyCompletenessScore,
    clothingVisibilityScore: detection.clothingVisibilityScore,
    backgroundReliabilityScore: detection.backgroundReliabilityScore,
  };
}

function clampScore(value: number): number {
  return Math.min(1, Math.max(0, Number(value.toFixed(4))));
}

function createFileNonce(): string {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID() : String(Date.now());
}
