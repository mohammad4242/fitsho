import type { BodyPhotoView } from "./types";
import type {
  BodyLandmarkDetection,
  BodyLandmarkDetector,
  DecodedBodyPhoto,
  NormalizedBodyLandmark,
} from "./processor";

type PoseLandmarkerLike = {
  detect(image: CanvasImageSource): { landmarks: NormalizedBodyLandmark[][]; close?: () => void };
  setOptions?: (options: Record<string, unknown>) => Promise<void> | void;
};

type PoseLandmarkerLoader = () => Promise<PoseLandmarkerLike>;

type MediaPipeVisionModule = {
  FilesetResolver: { forVisionTasks(basePath: string): Promise<unknown> };
  PoseLandmarker: {
    createFromOptions(
      fileset: unknown,
      options: Record<string, unknown>,
    ): Promise<PoseLandmarkerLike>;
  };
};

export const mediaPipePoseAssets = {
  modelAssetPath: "/mediapipe/models/pose_landmarker_lite.task",
  wasmBasePath: "/mediapipe/wasm",
} as const;

export class MediaPipePoseLandmarkDetector implements BodyLandmarkDetector {
  private readonly loader: PoseLandmarkerLoader;
  private detectorPromise: Promise<PoseLandmarkerLike> | null = null;

  constructor(loader: PoseLandmarkerLoader = loadMediaPipePoseLandmarker) {
    this.loader = loader;
  }

  async detect(image: DecodedBodyPhoto, view?: BodyPhotoView): Promise<BodyLandmarkDetection> {
    const detector = await this.getDetector();
    if (detector.setOptions !== undefined) {
      const isSide = view === "side";
      await detector.setOptions({
        minPoseDetectionConfidence: isSide ? 0.20 : 0.40,
        minPosePresenceConfidence: isSide ? 0.20 : 0.35,
      });
    }
    const result = detector.detect(image.source);
    try {
      return { poses: result.landmarks };
    } finally {
      result.close?.();
    }
  }

  private getDetector(): Promise<PoseLandmarkerLike> {
    this.detectorPromise ??= this.loader();
    return this.detectorPromise;
  }
}

export function createMediaPipePoseLandmarkerLoader(
  assets = mediaPipePoseAssets,
  loadVision: () => Promise<MediaPipeVisionModule> = loadMediaPipeVision,
  view?: BodyPhotoView,
): PoseLandmarkerLoader {
  return async () => {
    const { FilesetResolver, PoseLandmarker } = await loadVision();
    const fileset = await FilesetResolver.forVisionTasks(assets.wasmBasePath);
    const isSide = view === "side";
    return PoseLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: assets.modelAssetPath },
      runningMode: "IMAGE",
      numPoses: 2,
      minPoseDetectionConfidence: isSide ? 0.20 : 0.40,
      minPosePresenceConfidence: isSide ? 0.20 : 0.35,
    });
  };
}

async function loadMediaPipePoseLandmarker(): Promise<PoseLandmarkerLike> {
  return createMediaPipePoseLandmarkerLoader()();
}

async function loadMediaPipeVision(): Promise<MediaPipeVisionModule> {
  const vision = await import("@mediapipe/tasks-vision");
  return {
    FilesetResolver: vision.FilesetResolver,
    PoseLandmarker: {
      createFromOptions: async (fileset, options) => {
        const landmarker = await vision.PoseLandmarker.createFromOptions(
          fileset as never,
          options as never,
        );
        return {
          detect: (image) => landmarker.detect(image as never),
          setOptions: (opts) => landmarker.setOptions?.(opts as never),
        };
      },
    },
  };
}
