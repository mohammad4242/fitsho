// Web adapter: CSS transforms, browser decoding, canvas, and object URLs stay here.
import {
  clampGhostPhotoTransform,
  createGhostPhotoRenderPlan,
} from "@fitician/core/body-ghost-editor";
import type { GhostOverlayVariant } from "@fitician/core/body-ghost";
import type { GhostPhotoTransform } from "@fitician/core/body-ghost-editor";
import { GHOST_SCALE_MAX, GHOST_SCALE_MIN } from "./ghostScale";
import type { BodyPhotoView } from "./types";

export {
  GHOST_EDITOR_DEFAULT_TRANSFORM,
  GHOST_EDITOR_OUTPUT,
  GHOST_EDITOR_TOLERANCE,
  clampGhostPhotoTransform,
  containImageRect,
  createGhostPhotoRenderPlan,
  isGhostFramingWithinTolerance,
  privacyCropSourceYForView,
} from "@fitician/core/body-ghost-editor";
export type {
  GhostContainedImageRect,
  GhostDisplaySize,
  GhostPhotoRenderPlan,
  GhostPhotoTransform,
} from "@fitician/core/body-ghost-editor";
export {
  GHOST_BACK_PRIVACY_CUT_RATIO,
  GHOST_PRIVACY_CUT_RATIO,
  GHOST_SIDE_PRIVACY_CUT_RATIO,
  ghostPrivacyCutRatioForView,
  ghostPrivacyLineGeometry,
} from "./ghostGeometry";
export type { GhostPoint, GhostPrivacyLine as GhostPrivacyLineGeometry } from "@fitician/core/body-ghost";

export function ghostPercentage(value: number): string {
  return `${formatNumber(value * 100)}%`;
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
  const safeScale = Math.min(GHOST_SCALE_MAX, Math.max(GHOST_SCALE_MIN, Number.isFinite(scale) ? scale : 1));
  const mirror = mirrored ? "scaleX(-1) " : "";
  return `${mirror}scale(${formatNumber(safeScale)})`;
}

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

export function renderGhostPhoto(
  file: File,
  transform: GhostPhotoTransform,
  view?: BodyPhotoView,
  ghostScale?: number,
  runtime?: GhostPhotoCanvasRuntime,
  variant?: GhostOverlayVariant,
): Promise<File>;

export function renderGhostPhoto(
  file: File,
  transform: GhostPhotoTransform,
  view: BodyPhotoView,
  runtime: GhostPhotoCanvasRuntime,
  variant?: GhostOverlayVariant,
): Promise<File>;

export async function renderGhostPhoto(
  file: File,
  transform: GhostPhotoTransform,
  view: BodyPhotoView = "front",
  ghostScaleOrRuntime: number | GhostPhotoCanvasRuntime = 1,
  runtimeOrVariant: GhostPhotoCanvasRuntime | GhostOverlayVariant = browserGhostPhotoCanvasRuntime,
  variant: GhostOverlayVariant = "male",
): Promise<File> {
  const ghostScale = typeof ghostScaleOrRuntime === "number" ? ghostScaleOrRuntime : 1;
  const canvasRuntime = typeof ghostScaleOrRuntime === "number"
    ? isGhostPhotoCanvasRuntime(runtimeOrVariant) ? runtimeOrVariant : browserGhostPhotoCanvasRuntime
    : ghostScaleOrRuntime;
  const resolvedVariant = typeof ghostScaleOrRuntime === "number"
    ? variant
    : isGhostOverlayVariant(runtimeOrVariant) ? runtimeOrVariant : "male";
  const image = await canvasRuntime.decode(file);
  try {
    const plan = createGhostPhotoRenderPlan(
      image.width,
      image.height,
      transform,
      view,
      ghostScale,
      resolvedVariant,
    );
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

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
}

function createFileNonce(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
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

function isGhostOverlayVariant(value: unknown): value is GhostOverlayVariant {
  return value === "male" || value === "female" || value === "neutral";
}

function isGhostPhotoCanvasRuntime(value: unknown): value is GhostPhotoCanvasRuntime {
  return typeof value === "object"
    && value !== null
    && "decode" in value
    && "createCanvas" in value
    && "toJpeg" in value;
}

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
