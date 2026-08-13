import type {
  BodyLandmarkDetection,
  BodyLandmarkDetector,
  DecodedBodyPhoto,
  NormalizedBodyLandmark,
} from "./processor";

type PoseLandmarkerLike = {
  detect(image: CanvasImageSource): { landmarks: NormalizedBodyLandmark[][]; close?: () => void };
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

  async detect(image: DecodedBodyPhoto): Promise<BodyLandmarkDetection> {
    const detector = await this.getDetector();
    const result = detector.detect(image.source);
    try {
      return {
        personCount: result.landmarks.length,
        landmarks: result.landmarks.length === 1 ? result.landmarks[0] : [],
      };
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
): PoseLandmarkerLoader {
  return async () => {
    const { FilesetResolver, PoseLandmarker } = await loadVision();
    const fileset = await FilesetResolver.forVisionTasks(assets.wasmBasePath);
    return PoseLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: assets.modelAssetPath },
      runningMode: "IMAGE",
      numPoses: 2,
      minPoseDetectionConfidence: 0.55,
      minPosePresenceConfidence: 0.55,
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
        };
      },
    },
  };
}
