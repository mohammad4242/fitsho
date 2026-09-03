import {
  GHOST_SCALE_MAX,
  GHOST_SCALE_MIN,
  PHOTO_SCALE_MAX,
  PHOTO_SCALE_MIN,
} from "./ghostScale";
import type { BodyPhotoView, GhostTransform } from "./types";

export const GHOST_EDITOR_OUTPUT = {
  width: 1200,
  height: 1800,
} as const;

export const GHOST_PRIVACY_CUT_RATIO = 0.16;
export const GHOST_BACK_PRIVACY_CUT_RATIO = 0.08;
export const GHOST_EDITOR_TOLERANCE = 0.15;

const minimumPhotoScale = PHOTO_SCALE_MIN;
const maximumPhotoScale = PHOTO_SCALE_MAX;
const minimumRotation = -180;
const maximumRotation = 180;
const minimumTranslation = -0.5;
const maximumTranslation = 0.5;

export type GhostPhotoTransform = GhostTransform;

export const GHOST_EDITOR_DEFAULT_TRANSFORM: GhostPhotoTransform = {
  scale: 1,
  translateX: 0,
  translateY: 0,
  rotation: 0,
};

export function ghostPrivacyCutRatioForView(view: BodyPhotoView): number {
  return view === "back" ? GHOST_BACK_PRIVACY_CUT_RATIO : GHOST_PRIVACY_CUT_RATIO;
}

export function ghostPercentage(value: number): string {
  return `${formatNumber(value * 100)}%`;
}

export type GhostPhotoRenderPlan = {
  canvasWidth: number;
  canvasHeight: number;
  sourceWidth: number;
  sourceHeight: number;
  baseScale: number;
  sourceCropY: number;
  privacyCutPixels: number;
  privacyLineDisplayY: number;
  draw: {
    translateX: number;
    translateY: number;
    rotationRadians: number;
    scale: number;
  };
};

export type GhostPoint = {
  x: number;
  y: number;
};

export type GhostPrivacyLineGeometry = {
  anchor: GhostPoint;
  start: GhostPoint;
  end: GhostPoint;
};

export type GhostDisplaySize = {
  width: number;
  height: number;
};

export type GhostContainedImageRect = GhostDisplaySize & {
  x: number;
  y: number;
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
  drawImage: (image: CanvasImageSource, x: number, y: number) => void;
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
    translateX: clamp(transform.translateX, minimumTranslation, maximumTranslation),
    translateY: clamp(transform.translateY, minimumTranslation, maximumTranslation),
    scale: clamp(transform.scale, minimumPhotoScale, maximumPhotoScale),
    rotation: clamp(transform.rotation, minimumRotation, maximumRotation),
  };
}

export function ghostPhotoTransformStyle(
  transform: GhostPhotoTransform,
  mirrored = false,
): string {
  const safeTransform = clampGhostPhotoTransform(transform);
  const mirror = mirrored ? "scaleX(-1) " : "";
  return `${mirror}translate(-50%, -50%) translate(${formatNumber(safeTransform.translateX * 100)}%, ${formatNumber(safeTransform.translateY * 100)}%) rotate(${formatNumber(safeTransform.rotation)}deg) scale(${formatNumber(safeTransform.scale)})`;
}

export function ghostGuideTransformStyle(scale: number, mirrored = false): string {
  const safeScale = clamp(scale, GHOST_SCALE_MIN, GHOST_SCALE_MAX);
  const mirror = mirrored ? "scaleX(-1) " : "";
  return `${mirror}scale(${formatNumber(safeScale)})`;
}

export function isGhostFramingWithinTolerance(
  transform: GhostPhotoTransform,
  tolerance = GHOST_EDITOR_TOLERANCE,
): boolean {
  const safeTolerance = clamp(tolerance, 0, 1);
  return Math.abs(transform.translateX) <= safeTolerance
    && Math.abs(transform.translateY) <= safeTolerance;
}

export function ghostPrivacyLineGeometry(
  view: BodyPhotoView,
  ghostScale = 1,
  mirrored = false,
): GhostPrivacyLineGeometry {
  const safeScale = clamp(ghostScale, GHOST_SCALE_MIN, GHOST_SCALE_MAX);
  const transformedAnchor = transformGhostGuidePoint(
    { x: 0.5, y: ghostPrivacyCutRatioForView(view) },
    safeScale,
  );
  // The privacy boundary is a horizontal raster crop. Its row follows the
  // centered Ghost neck anchor so the visible line and encoded crop agree.
  const halfLineLength = safeScale / 2;
  const transformedStart = {
    x: transformedAnchor.x - halfLineLength,
    y: transformedAnchor.y,
  };
  const transformedEnd = {
    x: transformedAnchor.x + halfLineLength,
    y: transformedAnchor.y,
  };
  if (mirrored) {
    return {
      anchor: mirrorGhostPoint(transformedAnchor),
      start: mirrorGhostPoint(transformedEnd),
      end: mirrorGhostPoint(transformedStart),
    };
  }
  return {
    anchor: transformedAnchor,
    start: transformedStart,
    end: transformedEnd,
  };
}

export function containImageRect(
  container: GhostDisplaySize,
  source: GhostDisplaySize,
): GhostContainedImageRect {
  if (container.width <= 0 || container.height <= 0 || source.width <= 0 || source.height <= 0) {
    throw new Error("Ghost image dimensions must be positive");
  }
  const scale = Math.min(container.width / source.width, container.height / source.height);
  const width = source.width * scale;
  const height = source.height * scale;
  return {
    x: (container.width - width) / 2,
    y: (container.height - height) / 2,
    width,
    height,
  };
}

export function privacyCropSourceYForView(
  view: BodyPhotoView,
  ghostScale: number,
  displaySize: GhostDisplaySize,
  sourceSize: GhostDisplaySize,
): number {
  const line = ghostPrivacyLineGeometry(view, ghostScale);
  const imageRect = containImageRect(displaySize, sourceSize);
  const displayY = line.anchor.y * displaySize.height;
  return clamp(
    ((displayY - imageRect.y) / imageRect.height) * sourceSize.height,
    0,
    sourceSize.height,
  );
}

export function createGhostPhotoRenderPlan(
  sourceWidth: number,
  sourceHeight: number,
  transform: GhostPhotoTransform,
  view: BodyPhotoView = "front",
  ghostScale = 1,
): GhostPhotoRenderPlan {
  if (sourceWidth <= 0 || sourceHeight <= 0) {
    throw new Error("Ghost photo source dimensions must be positive");
  }
  const baseScale = Math.min(
    GHOST_EDITOR_OUTPUT.width / sourceWidth,
    GHOST_EDITOR_OUTPUT.height / sourceHeight,
  );
  const safeTransform = clampGhostPhotoTransform(transform);
  const privacyLineDisplayY = Math.round(
    ghostPrivacyLineGeometry(view, ghostScale).anchor.y * GHOST_EDITOR_OUTPUT.height,
  );
  const sourceCropY = Math.round(privacyCropSourceYForView(
    view,
    ghostScale,
    GHOST_EDITOR_OUTPUT,
    { width: sourceWidth, height: sourceHeight },
  ));
  const privacyCutPixels = privacyLineDisplayY;
  return {
    canvasWidth: GHOST_EDITOR_OUTPUT.width,
    canvasHeight: Math.max(1, GHOST_EDITOR_OUTPUT.height - privacyCutPixels),
    sourceWidth,
    sourceHeight,
    baseScale,
    sourceCropY,
    privacyCutPixels,
    privacyLineDisplayY,
    draw: {
      translateX: GHOST_EDITOR_OUTPUT.width / 2
        + safeTransform.translateX * GHOST_EDITOR_OUTPUT.width,
      translateY: GHOST_EDITOR_OUTPUT.height / 2
        - privacyCutPixels
        + safeTransform.translateY * GHOST_EDITOR_OUTPUT.height,
      rotationRadians: safeTransform.rotation * Math.PI / 180,
      scale: baseScale * safeTransform.scale,
    },
  };
}

export function renderGhostPhoto(
  file: File,
  transform: GhostPhotoTransform,
  view?: BodyPhotoView,
  ghostScale?: number,
  runtime?: GhostPhotoCanvasRuntime,
): Promise<File>;

export function renderGhostPhoto(
  file: File,
  transform: GhostPhotoTransform,
  view: BodyPhotoView,
  runtime: GhostPhotoCanvasRuntime,
): Promise<File>;

export async function renderGhostPhoto(
  file: File,
  transform: GhostPhotoTransform,
  view: BodyPhotoView = "front",
  ghostScaleOrRuntime: number | GhostPhotoCanvasRuntime = 1,
  runtime: GhostPhotoCanvasRuntime = browserGhostPhotoCanvasRuntime,
): Promise<File> {
  const ghostScale = typeof ghostScaleOrRuntime === "number" ? ghostScaleOrRuntime : 1;
  const canvasRuntime = typeof ghostScaleOrRuntime === "number" ? runtime : ghostScaleOrRuntime;
  const image = await canvasRuntime.decode(file);
  try {
    const plan = createGhostPhotoRenderPlan(image.width, image.height, transform, view, ghostScale);
    const canvas = canvasRuntime.createCanvas(plan.canvasWidth, plan.canvasHeight);
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

    const blob = await canvasRuntime.toJpeg(canvas, 0.9);
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

function transformGhostGuidePoint(point: GhostPoint, scale: number): GhostPoint {
  const relativeX = (point.x - 0.5) * scale;
  const relativeY = (point.y - 0.5) * scale;
  return {
    x: 0.5 + relativeX,
    y: 0.5 + relativeY,
  };
}

function mirrorGhostPoint(point: GhostPoint): GhostPoint {
  return { x: 1 - point.x, y: point.y };
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
