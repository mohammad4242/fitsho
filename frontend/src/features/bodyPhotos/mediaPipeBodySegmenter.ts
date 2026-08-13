import type {
  BodyPhotoSegmenter,
  BodySegmentationMask,
  DecodedBodyPhoto,
} from "./processor";

type MaskLike = {
  width: number;
  height: number;
  getAsFloat32Array(): Float32Array;
  close(): void;
};

type SegmentationResultLike = {
  confidenceMasks?: MaskLike[];
  close?: () => void;
};

type ImageSegmenterLike = {
  segment(image: CanvasImageSource): SegmentationResultLike;
};

type ImageSegmenterLoader = () => Promise<ImageSegmenterLike>;

type MediaPipeVisionModule = {
  FilesetResolver: { forVisionTasks(basePath: string): Promise<unknown> };
  ImageSegmenter: {
    createFromOptions(
      fileset: unknown,
      options: Record<string, unknown>,
    ): Promise<ImageSegmenterLike>;
  };
};

export const mediaPipeSegmentationAssets = {
  modelAssetPath: "/mediapipe/models/selfie_segmenter.tflite",
  wasmBasePath: "/mediapipe/wasm",
} as const;

export class MediaPipeBodySegmenter implements BodyPhotoSegmenter {
  private readonly loader: ImageSegmenterLoader;
  private segmenterPromise: Promise<ImageSegmenterLike> | null = null;

  constructor(loader: ImageSegmenterLoader = loadMediaPipeImageSegmenter) {
    this.loader = loader;
  }

  async segment(image: DecodedBodyPhoto): Promise<BodySegmentationMask> {
    const segmenter = await this.getSegmenter();
    const result = segmenter.segment(image.source);
    const mask = result.confidenceMasks?.[0];
    if (mask === undefined) {
      result.close?.();
      throw new Error("person segmentation mask unavailable");
    }
    try {
      return {
        width: mask.width,
        height: mask.height,
        confidence: new Float32Array(mask.getAsFloat32Array()),
      };
    } finally {
      mask.close();
      result.close?.();
    }
  }

  private getSegmenter(): Promise<ImageSegmenterLike> {
    this.segmenterPromise ??= this.loader();
    return this.segmenterPromise;
  }
}

export function createMediaPipeImageSegmenterLoader(
  assets = mediaPipeSegmentationAssets,
  loadVision: () => Promise<MediaPipeVisionModule> = loadMediaPipeVision,
): ImageSegmenterLoader {
  return async () => {
    const { FilesetResolver, ImageSegmenter } = await loadVision();
    const fileset = await FilesetResolver.forVisionTasks(assets.wasmBasePath);
    return ImageSegmenter.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: assets.modelAssetPath },
      runningMode: "IMAGE",
      outputConfidenceMasks: true,
      outputCategoryMask: false,
    });
  };
}

async function loadMediaPipeImageSegmenter(): Promise<ImageSegmenterLike> {
  return createMediaPipeImageSegmenterLoader()();
}

async function loadMediaPipeVision(): Promise<MediaPipeVisionModule> {
  const vision = await import("@mediapipe/tasks-vision");
  return {
    FilesetResolver: vision.FilesetResolver,
    ImageSegmenter: {
      createFromOptions: async (fileset, options) => {
        const segmenter = await vision.ImageSegmenter.createFromOptions(
          fileset as never,
          options as never,
        );
        return {
          segment: (image) => segmenter.segment(image as never) as SegmentationResultLike,
        };
      },
    },
  };
}
