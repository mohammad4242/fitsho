import type { BodyPhotoView } from "./types";

export const GHOST_EDITOR_OUTPUT = {
  width: 1200,
  height: 1800,
} as const;

export const GHOST_PRIVACY_CUT_RATIO = 0.16;
export const GHOST_BACK_PRIVACY_CUT_RATIO = 0.08;
export const GHOST_EDITOR_OUTPUT_HEIGHT = Math.round(
  GHOST_EDITOR_OUTPUT.height * (1 - GHOST_PRIVACY_CUT_RATIO),
);
export const GHOST_EDITOR_TOLERANCE = 0.15;

const minimumScale = 0.75;
const maximumScale = 2.5;
const minimumRotation = -180;
const maximumRotation = 180;
const maximumOffset = 900;

export type GhostPhotoTransform = {
  offsetX: number;
  offsetY: number;
  scale: number;
  rotation: number;
};

export const GHOST_EDITOR_DEFAULT_TRANSFORM: GhostPhotoTransform = {
  offsetX: 0,
  offsetY: 0,
  scale: 1,
  rotation: 0,
};

export function ghostPrivacyCutRatioForView(view: BodyPhotoView): number {
  return view === "back" ? GHOST_BACK_PRIVACY_CUT_RATIO : GHOST_PRIVACY_CUT_RATIO;
}

export function ghostEditorOutputHeightForView(view: BodyPhotoView): number {
  return Math.round(GHOST_EDITOR_OUTPUT.height * (1 - ghostPrivacyCutRatioForView(view)));
}

export type GhostPhotoRenderPlan = {
  canvasWidth: number;
  canvasHeight: number;
  sourceWidth: number;
  sourceHeight: number;
  baseScale: number;
  privacyCutPixels: number;
  draw: {
    translateX: number;
    translateY: number;
    rotationRadians: number;
    scale: number;
  };
};

export type DecodedGhostPhoto = {
  source: CanvasImageSource;
  width: number;
  height: number;
  dispose: () => void;
};

export type GhostPhotoCanvasContext = {
  fillStyle: string | CanvasGradient | CanvasPattern;
  fillRect: (x: number, y: number, width: number, height: number) => void;
  save: () => void;
  translate: (x: number, y: number) => void;
  rotate: (angle: number) => void;
  scale: (x: number, y: number) => void;
  drawImage: (
    image: CanvasImageSource,
    dx: number,
    dy: number,
  ) => void;
  restore: () => void;
};

export type GhostPhotoCanvas = {
  width: number;
  height: number;
  getContext: (contextId: "2d") => GhostPhotoCanvasContext | null;
};

export type GhostPhotoCanvasRuntime = {
  decode: (file: File) => Promise<DecodedGhostPhoto>;
  createCanvas: (width: number, height: number) => GhostPhotoCanvas;
  toJpeg: (canvas: GhostPhotoCanvas, quality: number) => Promise<Blob>;
};

export function clampGhostPhotoTransform(
  transform: GhostPhotoTransform,
): GhostPhotoTransform {
  return {
    offsetX: clamp(transform.offsetX, -maximumOffset, maximumOffset),
    offsetY: clamp(transform.offsetY, -maximumOffset, maximumOffset),
    scale: clamp(transform.scale, minimumScale, maximumScale),
    rotation: clamp(transform.rotation, minimumRotation, maximumRotation),
  };
}

export function ghostPhotoTransformStyle(transform: GhostPhotoTransform): string {
  const safeTransform = clampGhostPhotoTransform(transform);
  return `translate(-50%, -50%) translate(${formatNumber(safeTransform.offsetX)}px, ${formatNumber(safeTransform.offsetY)}px) rotate(${formatNumber(safeTransform.rotation)}deg) scale(${formatNumber(safeTransform.scale)})`;
}

export function isGhostFramingWithinTolerance(
  transform: GhostPhotoTransform,
  tolerance = GHOST_EDITOR_TOLERANCE,
): boolean {
  const safeTolerance = clamp(tolerance, 0, 1);
  return Math.abs(transform.offsetX) <= GHOST_EDITOR_OUTPUT.width * safeTolerance
    && Math.abs(transform.offsetY) <= GHOST_EDITOR_OUTPUT.height * safeTolerance;
}

export function createGhostPhotoRenderPlan(
  sourceWidth: number,
  sourceHeight: number,
  transform: GhostPhotoTransform,
  view: BodyPhotoView = "front",
): GhostPhotoRenderPlan {
  if (sourceWidth <= 0 || sourceHeight <= 0) {
    throw new Error("Ghost photo source dimensions must be positive");
  }
  const safeTransform = clampGhostPhotoTransform(transform);
  const baseScale = Math.min(
    GHOST_EDITOR_OUTPUT.width / sourceWidth,
    GHOST_EDITOR_OUTPUT.height / sourceHeight,
  );
  const privacyCutPixels = Math.round(
    GHOST_EDITOR_OUTPUT.height * ghostPrivacyCutRatioForView(view),
  );
  return {
    canvasWidth: GHOST_EDITOR_OUTPUT.width,
    canvasHeight: ghostEditorOutputHeightForView(view),
    sourceWidth,
    sourceHeight,
    baseScale,
    privacyCutPixels,
    draw: {
      translateX: GHOST_EDITOR_OUTPUT.width / 2 + safeTransform.offsetX,
      translateY: GHOST_EDITOR_OUTPUT.height / 2 - privacyCutPixels + safeTransform.offsetY,
      rotationRadians: safeTransform.rotation * Math.PI / 180,
      scale: baseScale * safeTransform.scale,
    },
  };
}

export async function renderGhostPhoto(
  file: File,
  transform: GhostPhotoTransform,
  view: BodyPhotoView = "front",
  runtime: GhostPhotoCanvasRuntime = browserGhostPhotoCanvasRuntime,
): Promise<File> {
  const image = await runtime.decode(file);
  try {
    const plan = createGhostPhotoRenderPlan(image.width, image.height, transform, view);
    const canvas = runtime.createCanvas(plan.canvasWidth, plan.canvasHeight);
    canvas.width = plan.canvasWidth;
    canvas.height = plan.canvasHeight;
    const context = canvas.getContext("2d");
    if (context === null) throw new Error("Ghost photo canvas is unavailable");

    context.fillStyle = "rgb(160, 163, 161)";
    context.fillRect(0, 0, plan.canvasWidth, plan.canvasHeight);
    context.save();
    context.translate(plan.draw.translateX, plan.draw.translateY);
    context.rotate(plan.draw.rotationRadians);
    context.scale(plan.draw.scale, plan.draw.scale);
    context.drawImage(image.source, -plan.sourceWidth / 2, -plan.sourceHeight / 2);
    context.restore();

    const blob = await runtime.toJpeg(canvas, 0.9);
    if (blob.size === 0 || blob.type !== "image/jpeg") {
      throw new Error("Ghost photo output is unavailable");
    }
    return new File([blob], `body-photo-edited-${createFileNonce()}.jpg`, {
      type: "image/jpeg",
      lastModified: Date.now(),
    });
  } finally {
    image.dispose();
  }
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, Number.isFinite(value) ? value : 0));
}

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}

function createFileNonce(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

const browserGhostPhotoCanvasRuntime: GhostPhotoCanvasRuntime = {
  async decode(file) {
    if (typeof createImageBitmap === "function") {
      const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
      return {
        source: bitmap,
        width: bitmap.width,
        height: bitmap.height,
        dispose: () => bitmap.close(),
      };
    }
    return decodeWithImageElement(file);
  },
  createCanvas(width, height) {
    if (typeof document === "undefined") throw new Error("Ghost photo canvas is unavailable");
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    return canvas;
  },
  toJpeg(canvas, quality) {
    return new Promise((resolve, reject) => {
      const nativeCanvas = canvas as HTMLCanvasElement;
      nativeCanvas.toBlob((blob) => {
        if (blob === null) {
          reject(new Error("Ghost photo output is unavailable"));
          return;
        }
        resolve(blob);
      }, "image/jpeg", quality);
    });
  },
};

function decodeWithImageElement(file: File): Promise<DecodedGhostPhoto> {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file);
    const image = new Image();
    const release = () => URL.revokeObjectURL(objectUrl);
    image.onload = () => {
      release();
      if (image.naturalWidth <= 0 || image.naturalHeight <= 0) {
        reject(new Error("Ghost photo image is invalid"));
        return;
      }
      resolve({
        source: image,
        width: image.naturalWidth,
        height: image.naturalHeight,
        dispose: () => { image.src = ""; },
      });
    };
    image.onerror = () => {
      release();
      reject(new Error("Ghost photo image is invalid"));
    };
    image.src = objectUrl;
  });
}
