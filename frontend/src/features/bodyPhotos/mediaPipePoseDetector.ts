import type {
  BodyLandmarkDetection,
  BodyLandmarkDetector,
  DecodedBodyPhoto,
} from "./processor";
import type { BodyPhotoView } from "./types";

type Landmark = { x: number; y: number; visibility?: number };

export type PoseLandmarkerLike = {
  detect(image: CanvasImageSource): { landmarks: Landmark[][] };
};

type PoseLandmarkerLoader = () => Promise<PoseLandmarkerLike>;

type FaceDetectorLike = {
  detect(image: CanvasImageSource): { detections: Array<{ boundingBox?: { originY: number; height: number } }> };
};

type FaceDetectorLoader = () => Promise<FaceDetectorLike>;

type MediaPipeVisionModule = {
  FilesetResolver: { forVisionTasks(basePath: string): Promise<unknown> };
  PoseLandmarker: {
    createFromOptions(fileset: unknown, options: Record<string, unknown>): Promise<PoseLandmarkerLike>;
  };
  FaceDetector: {
    createFromOptions(fileset: unknown, options: Record<string, unknown>): Promise<FaceDetectorLike>;
  };
};

const visibilityIndices = [0, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28];
export const mediaPipePoseAssets = {
  modelAssetPath: "/mediapipe/models/pose_landmarker_lite.task",
  wasmBasePath: "/mediapipe/wasm",
} as const;

export const mediaPipeFaceAssets = {
  modelAssetPath: "/mediapipe/models/blaze_face_short_range.tflite",
  wasmBasePath: mediaPipePoseAssets.wasmBasePath,
} as const;

/**
 * Real on-device landmark adapter. The model download contains only model assets;
 * the selected image stays in browser memory and is never sent to that URL.
 */
export class MediaPipePoseLandmarkDetector implements BodyLandmarkDetector {
  private loader: PoseLandmarkerLoader;
  private faceLoader: FaceDetectorLoader;
  private landmarkerPromise: Promise<PoseLandmarkerLike> | null = null;
  private faceDetectorPromise: Promise<FaceDetectorLike | null> | null = null;

  constructor(
    loader: PoseLandmarkerLoader = loadMediaPipeLandmarker,
    faceLoader: FaceDetectorLoader = loadMediaPipeFaceDetector,
  ) {
    this.loader = loader;
    this.faceLoader = faceLoader;
  }

  async detect(image: DecodedBodyPhoto, expectedView: BodyPhotoView): Promise<BodyLandmarkDetection> {
    const landmarker = await this.getLandmarker();
    const result = landmarker.detect(image.source);
    const poses = result.landmarks;
    if (poses.length !== 1) return rejectedDetection(poses.length);

    const landmarks = poses[0];
    const visibility = averageVisibility(landmarks);
    const leftShoulder = landmarks[11];
    const rightShoulder = landmarks[12];
    if (!leftShoulder || !rightShoulder) {
      return incompleteDetection(expectedView, visibility);
    }

    const shoulderLineY = Math.min(leftShoulder.y, rightShoulder.y);
    const faceBottomY = await this.detectFaceBottom(image) ?? poseFaceBottom(landmarks);
    if (faceBottomY === null) return incompleteDetection(expectedView, visibility);
    // Crop immediately above the shoulder line, but only when it remains safely
    // below every observed head/face landmark. This removes the visible head rather
    // than applying a fixed image-percentage crop.
    const candidateCropY = shoulderLineY - 0.012;
    const safeHeadCropY = candidateCropY >= faceBottomY + 0.04
      ? candidateCropY
      : null;
    const shoulderSpan = Math.abs(leftShoulder.x - rightShoulder.x);
    const detectedView = expectedView === "side"
      ? viewMatchesGeometry("side", shoulderSpan) ? "side" : "unknown"
      : expectedView;
    const completeness = bodyCompleteness(landmarks);
    // Pose landmarks do not validate clothing, relevance, or background. Those
    // checks remain guidance-only until a purpose-built on-device policy exists.
    const clothingVisibilityScore = 0;
    const poseScore = Math.min(1, (visibility + completeness) / 2);

    return {
      personCount: 1,
      detectedView,
      detectionConfidence: visibility,
      poseScore,
      bodyCompletenessScore: completeness,
      clothingVisibilityScore,
      backgroundReliabilityScore: 0,
      isSafeAndRelevant: false,
      clothingValidation: "unavailable",
      contentSafetyValidation: "unavailable",
      backgroundValidation: "unavailable",
      faceBottomY,
      safeHeadCropY,
      shoulderLineY,
      headFullyExcluded: safeHeadCropY !== null,
      shouldersPreserved: safeHeadCropY !== null,
      headCropConfidence: safeHeadCropY === null ? 0 : Math.min(1, visibility),
      warnings: [],
    };
  }

  private getLandmarker(): Promise<PoseLandmarkerLike> {
    if (this.landmarkerPromise === null) {
      this.landmarkerPromise = this.loader().catch((error: unknown) => {
        this.landmarkerPromise = null;
        throw error;
      });
    }
    return this.landmarkerPromise;
  }

  private getFaceDetector(): Promise<FaceDetectorLike | null> {
    if (this.faceDetectorPromise === null) {
      this.faceDetectorPromise = this.faceLoader().catch(() => null);
    }
    return this.faceDetectorPromise;
  }

  private async detectFaceBottom(image: DecodedBodyPhoto): Promise<number | null> {
    const detector = await this.getFaceDetector();
    if (detector === null) return null;
    const detections = detector.detect(image.source).detections;
    if (detections.length !== 1) return null;
    const box = detections[0]?.boundingBox;
    if (box === undefined || box.height <= 0 || image.height <= 0) return null;
    const bottom = (box.originY + box.height) / image.height;
    return Number.isFinite(bottom) && bottom > 0 && bottom < 0.5 ? bottom : null;
  }
}

export function createMediaPipePoseLandmarkLoader(
  assets = mediaPipePoseAssets,
  loadVision: () => Promise<MediaPipeVisionModule> = loadMediaPipeVision,
): PoseLandmarkerLoader {
  return async () => {
    const { FilesetResolver, PoseLandmarker } = await loadVision();
    const fileset = await FilesetResolver.forVisionTasks(assets.wasmBasePath);
    return PoseLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: assets.modelAssetPath },
      runningMode: "IMAGE",
      numPoses: 2,
      minPoseDetectionConfidence: 0.7,
      minPosePresenceConfidence: 0.7,
      minTrackingConfidence: 0.7,
      outputSegmentationMasks: true,
    });
  };
}

async function loadMediaPipeLandmarker(): Promise<PoseLandmarkerLike> {
  return createMediaPipePoseLandmarkLoader()();
}

export function createMediaPipeFaceDetectorLoader(
  assets = mediaPipeFaceAssets,
  loadVision: () => Promise<MediaPipeVisionModule> = loadMediaPipeVision,
): FaceDetectorLoader {
  return async () => {
    const { FilesetResolver, FaceDetector } = await loadVision();
    const fileset = await FilesetResolver.forVisionTasks(assets.wasmBasePath);
    return FaceDetector.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: assets.modelAssetPath },
      runningMode: "IMAGE",
      minDetectionConfidence: 0.7,
    });
  };
}

async function loadMediaPipeFaceDetector(): Promise<FaceDetectorLike> {
  return createMediaPipeFaceDetectorLoader()();
}

async function loadMediaPipeVision(): Promise<MediaPipeVisionModule> {
  const vision = await import("@mediapipe/tasks-vision");
  return {
    FilesetResolver: vision.FilesetResolver,
    PoseLandmarker: {
      createFromOptions: async (fileset, options) => {
        const poseLandmarker = await vision.PoseLandmarker.createFromOptions(fileset as never, options as never);
        return {
          detect: (image) => poseLandmarker.detect(image as never) as { landmarks: Landmark[][] },
        };
      },
    },
    FaceDetector: {
      createFromOptions: async (fileset, options) => {
        const faceDetector = await vision.FaceDetector.createFromOptions(fileset as never, options as never);
        return {
          detect: (image) => faceDetector.detect(image as never) as { detections: Array<{ boundingBox?: { originY: number; height: number } }> },
        };
      },
    },
  };
}

function poseFaceBottom(landmarks: Landmark[]): number | null {
  const faceLandmarks = [landmarks[0], landmarks[7], landmarks[8]]
    .filter((landmark): landmark is Landmark => landmark !== undefined);
  if (faceLandmarks.length === 0) return null;
  return Math.max(...faceLandmarks.map((landmark) => landmark.y));
}

function rejectedDetection(personCount: number): BodyLandmarkDetection {
  return {
    personCount,
    detectedView: "unknown",
    detectionConfidence: 0,
    poseScore: 0,
    bodyCompletenessScore: 0,
    clothingVisibilityScore: 0,
    backgroundReliabilityScore: 0,
    isSafeAndRelevant: false,
    clothingValidation: "unavailable",
    contentSafetyValidation: "unavailable",
    backgroundValidation: "unavailable",
    faceBottomY: null,
    safeHeadCropY: null,
    shoulderLineY: null,
    headFullyExcluded: false,
    shouldersPreserved: false,
    headCropConfidence: 0,
    warnings: ["no_single_body_detected"],
  };
}

function incompleteDetection(view: BodyPhotoView, visibility: number): BodyLandmarkDetection {
  return {
    personCount: 1,
    detectedView: view,
    detectionConfidence: visibility,
    poseScore: visibility,
    bodyCompletenessScore: 0,
    clothingVisibilityScore: 0,
    backgroundReliabilityScore: 0,
    isSafeAndRelevant: false,
    clothingValidation: "unavailable",
    contentSafetyValidation: "unavailable",
    backgroundValidation: "unavailable",
    faceBottomY: null,
    safeHeadCropY: null,
    shoulderLineY: null,
    headFullyExcluded: false,
    shouldersPreserved: false,
    headCropConfidence: 0,
    warnings: ["required_landmarks_missing"],
  };
}

function averageVisibility(landmarks: Landmark[]): number {
  const visible = visibilityIndices
    .map((index) => landmarks[index]?.visibility ?? 0)
    .filter((score) => Number.isFinite(score));
  if (visible.length === 0) return 0;
  return visible.reduce((total, score) => total + score, 0) / visible.length;
}

function bodyCompleteness(landmarks: Landmark[]): number {
  const required = [11, 12, 23, 24, 25, 26, 27, 28];
  const scores = required.map((index) => landmarks[index]?.visibility ?? 0);
  return scores.reduce((total, score) => total + score, 0) / scores.length;
}

function viewMatchesGeometry(expectedView: BodyPhotoView, shoulderSpan: number): boolean {
  if (expectedView === "side") return shoulderSpan <= 0.2;
  return shoulderSpan >= 0.12;
}
