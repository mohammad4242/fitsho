import { MediaPipeBodySegmenter } from "./mediaPipeBodySegmenter";
import { MediaPipePoseLandmarkDetector } from "./mediaPipePoseDetector";
import type { BodyPhotoView } from "./types";

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

export type BodyPhotoValidation = {
  isValid: true;
  expectedView: BodyPhotoView;
  viewAssessment: "matched" | "ambiguous";
  quality: BodyPhotoQuality;
  visibleLandmarks: Array<"shoulders" | "arms" | "hips" | "knees" | "ankles" | "feet">;
};

export type ProcessedBodyPhoto = {
  file: File;
  previewUrl: string;
  validation: BodyPhotoValidation;
};

export interface BodyPhotoProcessor {
  process(file: File, view: BodyPhotoView): Promise<ProcessedBodyPhoto>;
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
  frameMargin: 0.005,
  targetWidth: 1200,
  outputQuality: 0.9,
  neutralGray: [160, 163, 161] as const,
} as const;

const landmarkGroups = {
  shoulders: [11, 12],
  elbows: [13, 14],
  wrists: [15, 16],
  hips: [23, 24],
  knees: [25, 26],
  ankles: [27, 28],
  feet: [31, 32],
} as const;

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

  async process(file: File, view: BodyPhotoView): Promise<ProcessedBodyPhoto> {
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
      const pose = validateLandmarks(detection, view);
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
          visibleLandmarks: ["shoulders", "arms", "hips", "knees", "ankles", "feet"],
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
};

function validateLandmarks(
  detection: BodyLandmarkDetection,
  expectedView: BodyPhotoView,
): ValidatedPose {
  const landmarks = selectPrimaryPose(detection.poses);
  const required = requiredLandmarksForView(landmarks, expectedView);
  if (required.some((landmark) => !insideFrame(landmark))) {
    throw new BodyPhotoProcessingError("body_out_of_frame");
  }

  const projection = projectedView(landmarks);
  if (
    (expectedView === "side" && projection === "non_side")
    || (expectedView !== "side" && projection === "side")
  ) {
    throw new BodyPhotoProcessingError("unexpected_body_view");
  }
  return {
    viewAssessment: (
      expectedView === "side" && projection === "side" ? "matched" : "ambiguous"
    ),
    minimumVisibility: clampScore(Math.min(...required.map((landmark) => landmark.visibility))),
  };
}

function requiredLandmarksForView(
  landmarks: NormalizedBodyLandmark[],
  view: BodyPhotoView,
): NormalizedBodyLandmark[] {
  if (view === "side") {
    return [
      mostVisible(landmarks, landmarkGroups.shoulders, "shoulders_not_visible"),
      mostVisible(landmarks, landmarkGroups.elbows, "arms_not_visible"),
      mostVisible(landmarks, landmarkGroups.hips, "torso_not_visible"),
      mostVisible(landmarks, landmarkGroups.knees, "legs_or_feet_not_visible"),
      mostVisible(landmarks, landmarkGroups.ankles, "legs_or_feet_not_visible"),
      mostVisible(landmarks, landmarkGroups.feet, "legs_or_feet_not_visible"),
    ];
  }

  requireVisible(landmarks, landmarkGroups.shoulders, "shoulders_not_visible");
  requireVisible(landmarks, landmarkGroups.elbows, "arms_not_visible");
  requireVisible(landmarks, landmarkGroups.wrists, "arms_not_visible");
  requireVisible(landmarks, landmarkGroups.hips, "torso_not_visible");
  requireVisible(landmarks, landmarkGroups.knees, "legs_or_feet_not_visible");
  requireVisible(landmarks, landmarkGroups.ankles, "legs_or_feet_not_visible");
  requireVisible(landmarks, landmarkGroups.feet, "legs_or_feet_not_visible");
  return Object.values(landmarkGroups)
    .flat()
    .map((index) => landmarks[index]!);
}

function mostVisible(
  landmarks: NormalizedBodyLandmark[],
  indices: readonly number[],
  code: BodyPhotoProcessingErrorCode,
): NormalizedBodyLandmark {
  const selected = indices
    .map((index) => landmarks[index])
    .filter((landmark): landmark is NormalizedBodyLandmark => landmark !== undefined)
    .sort((left, right) => right.visibility - left.visibility)[0];
  if (selected === undefined || selected.visibility < limits.minimumLandmarkVisibility) {
    throw new BodyPhotoProcessingError(code);
  }
  return selected;
}

type PoseBox = {
  left: number;
  top: number;
  right: number;
  bottom: number;
};

type PoseCandidate = {
  landmarks: NormalizedBodyLandmark[];
  box: PoseBox;
  area: number;
  reliability: number;
};

const poseBoxIndices = [
  ...landmarkGroups.shoulders,
  ...landmarkGroups.elbows,
  ...landmarkGroups.hips,
  ...landmarkGroups.knees,
  ...landmarkGroups.ankles,
  ...landmarkGroups.feet,
] as const;

function selectPrimaryPose(poses: NormalizedBodyLandmark[][]): NormalizedBodyLandmark[] {
  const candidates = poses
    .filter((pose) => pose.length >= 33)
    .map(toPoseCandidate)
    .sort((left, right) => (
      right.reliability - left.reliability || right.area - left.area
    ));
  const primary = candidates[0];
  if (primary === undefined) throw new BodyPhotoProcessingError("body_not_detected");

  const hasDistinctSecondary = candidates.slice(1).some((candidate) => (
    isCrediblePose(candidate.landmarks)
    && candidate.area >= primary.area * 0.25
    && intersectionOverUnion(primary.box, candidate.box) < 0.6
  ));
  if (hasDistinctSecondary) {
    throw new BodyPhotoProcessingError("multiple_people_detected");
  }
  return primary.landmarks;
}

function toPoseCandidate(landmarks: NormalizedBodyLandmark[]): PoseCandidate {
  const box = poseBox(landmarks);
  return {
    landmarks,
    box,
    area: boxArea(box),
    reliability: Object.values(landmarkGroups)
      .reduce((score, indices) => score + maximumVisibility(landmarks, indices), 0),
  };
}

function isCrediblePose(landmarks: NormalizedBodyLandmark[]): boolean {
  const visible = (indices: readonly number[]) => (
    maximumVisibility(landmarks, indices) >= limits.minimumLandmarkVisibility
  );
  const visibleLowerGroups = [landmarkGroups.knees, landmarkGroups.ankles, landmarkGroups.feet]
    .filter(visible).length;
  return visible(landmarkGroups.shoulders)
    && visible(landmarkGroups.elbows)
    && visible(landmarkGroups.hips)
    && visibleLowerGroups >= 2;
}

function maximumVisibility(
  landmarks: NormalizedBodyLandmark[],
  indices: readonly number[],
): number {
  return Math.max(...indices.map((index) => landmarks[index]?.visibility ?? 0));
}

function poseBox(landmarks: NormalizedBodyLandmark[]): PoseBox {
  const visible = poseBoxIndices
    .map((index) => landmarks[index])
    .filter((landmark): landmark is NormalizedBodyLandmark => (
      landmark !== undefined && landmark.visibility >= 0.2
    ));
  if (visible.length === 0) return { left: 0, top: 0, right: 0, bottom: 0 };
  return {
    left: Math.min(...visible.map((landmark) => landmark.x)),
    top: Math.min(...visible.map((landmark) => landmark.y)),
    right: Math.max(...visible.map((landmark) => landmark.x)),
    bottom: Math.max(...visible.map((landmark) => landmark.y)),
  };
}

function boxArea(box: PoseBox): number {
  return Math.max(0, box.right - box.left) * Math.max(0, box.bottom - box.top);
}

function intersectionOverUnion(left: PoseBox, right: PoseBox): number {
  const intersection = boxArea({
    left: Math.max(left.left, right.left),
    top: Math.max(left.top, right.top),
    right: Math.min(left.right, right.right),
    bottom: Math.min(left.bottom, right.bottom),
  });
  const union = boxArea(left) + boxArea(right) - intersection;
  return union <= 0 ? 0 : intersection / union;
}

function requireVisible(
  landmarks: NormalizedBodyLandmark[],
  indices: readonly number[],
  code: BodyPhotoProcessingErrorCode,
) {
  if (indices.some((index) => (landmarks[index]?.visibility ?? 0) < limits.minimumLandmarkVisibility)) {
    throw new BodyPhotoProcessingError(code);
  }
}

function insideFrame(landmark: NormalizedBodyLandmark): boolean {
  return landmark.x >= limits.frameMargin
    && landmark.x <= 1 - limits.frameMargin
    && landmark.y >= limits.frameMargin
    && landmark.y <= 1 - limits.frameMargin;
}

function projectedView(landmarks: NormalizedBodyLandmark[]): "side" | "non_side" | "ambiguous" {
  if (
    [...landmarkGroups.shoulders, ...landmarkGroups.hips]
      .some((index) => (landmarks[index]?.visibility ?? 0) < limits.minimumLandmarkVisibility)
  ) {
    return "ambiguous";
  }
  const shoulderSpan = Math.abs(landmarks[11]!.x - landmarks[12]!.x);
  const hipSpan = Math.abs(landmarks[23]!.x - landmarks[24]!.x);
  if (shoulderSpan <= 0.08 && hipSpan <= 0.08) return "side";
  if (shoulderSpan >= 0.16 && hipSpan >= 0.12) return "non_side";
  return "ambiguous";
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
  if (source.length !== width * height * 4 || mask.confidence.length !== mask.width * mask.height) {
    throw new BodyPhotoProcessingError("segmentation_unavailable");
  }
  const output = new Uint8ClampedArray(source.length);
  for (let y = 0; y < height; y += 1) {
    const maskY = Math.min(mask.height - 1, Math.floor((y / height) * mask.height));
    for (let x = 0; x < width; x += 1) {
      const maskX = Math.min(mask.width - 1, Math.floor((x / width) * mask.width));
      const confidence = Math.min(1, Math.max(0, mask.confidence[maskY * mask.width + maskX]!));
      const index = (y * width + x) * 4;
      output[index] = Math.round(source[index]! * confidence + background[0] * (1 - confidence));
      output[index + 1] = Math.round(source[index + 1]! * confidence + background[1] * (1 - confidence));
      output[index + 2] = Math.round(source[index + 2]! * confidence + background[2] * (1 - confidence));
      output[index + 3] = 255;
    }
  }
  return output;
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
