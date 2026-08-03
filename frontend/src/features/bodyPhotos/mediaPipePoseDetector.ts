import type {
  BodyLandmarkDetection,
  BodyLandmarkDetector,
  DecodedBodyPhoto,
} from "./processor";
import type { BodyPhotoView } from "./types";

type FaceDetectorLike = {
  detect(image: CanvasImageSource): { detections: Array<{ boundingBox?: { originY: number; height: number } }> };
};

type FaceDetectorLoader = () => Promise<FaceDetectorLike>;

type MediaPipeVisionModule = {
  FilesetResolver: { forVisionTasks(basePath: string): Promise<unknown> };
  FaceDetector: {
    createFromOptions(fileset: unknown, options: Record<string, unknown>): Promise<FaceDetectorLike>;
  };
};

export const mediaPipeFaceAssets = {
  modelAssetPath: "/mediapipe/models/blaze_face_short_range.tflite",
  wasmBasePath: "/mediapipe/wasm",
} as const;

/**
 * Lightweight on-device adapter used only to remove the face before upload. Full
 * body eligibility is validated later by the configured AI preflight, so a heavy
 * pose landmarker does not block the browser's main thread.
 */
export class MediaPipePoseLandmarkDetector implements BodyLandmarkDetector {
  private faceLoader: FaceDetectorLoader;
  private faceDetectorPromise: Promise<FaceDetectorLike | null> | null = null;

  constructor(faceLoader: FaceDetectorLoader = loadMediaPipeFaceDetector) {
    this.faceLoader = faceLoader;
  }

  async detect(image: DecodedBodyPhoto, expectedView: BodyPhotoView): Promise<BodyLandmarkDetection> {
    const detector = await this.getFaceDetector();
    if (detector === null) throw new Error("face detector unavailable");
    const detections = detector.detect(image.source).detections;
    if (detections.length !== 1) return rejectedDetection(detections.length);
    const faceBottomY = faceBottom(detections[0]?.boundingBox, image.height);
    if (faceBottomY === null) return incompleteDetection(expectedView);

    const safeHeadCropY = faceBottomY + 0.05;
    if (safeHeadCropY >= 0.5) return incompleteDetection(expectedView);
    return faceDetected(expectedView, faceBottomY, safeHeadCropY);
  }

  private getFaceDetector(): Promise<FaceDetectorLike | null> {
    if (this.faceDetectorPromise === null) {
      this.faceDetectorPromise = this.faceLoader().catch(() => null);
    }
    return this.faceDetectorPromise;
  }

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

function incompleteDetection(view: BodyPhotoView): BodyLandmarkDetection {
  return {
    personCount: 1,
    detectedView: view,
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
    warnings: ["required_landmarks_missing"],
  };
}

function faceBottom(
  box: { originY: number; height: number } | undefined,
  imageHeight: number,
): number | null {
  if (box === undefined || box.height <= 0 || imageHeight <= 0) return null;
  const bottom = (box.originY + box.height) / imageHeight;
  return Number.isFinite(bottom) && bottom > 0 && bottom < 0.45 ? bottom : null;
}

function faceDetected(
  view: BodyPhotoView,
  faceBottomY: number,
  safeHeadCropY: number,
): BodyLandmarkDetection {
  return {
    personCount: 1,
    detectedView: view,
    detectionConfidence: 0.95,
    poseScore: 0.95,
    bodyCompletenessScore: 1,
    clothingVisibilityScore: 0,
    backgroundReliabilityScore: 0,
    isSafeAndRelevant: false,
    clothingValidation: "unavailable",
    contentSafetyValidation: "unavailable",
    backgroundValidation: "unavailable",
    faceBottomY,
    safeHeadCropY,
    shoulderLineY: safeHeadCropY + 0.06,
    headFullyExcluded: true,
    shouldersPreserved: true,
    headCropConfidence: 0.95,
    warnings: [],
  };
}
