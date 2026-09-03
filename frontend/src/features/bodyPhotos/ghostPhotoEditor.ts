import { GHOST_SCALE_MAX, GHOST_SCALE_MIN } from "./ghostScale";
import type { BodyPhotoView, GhostTransform } from "./types";

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

const minimumScale = GHOST_SCALE_MIN;
const maximumScale = GHOST_SCALE_MAX;
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

export function ghostEditorOutputHeightForView(view: BodyPhotoView): number {
  return Math.round(GHOST_EDITOR_OUTPUT.height * (1 - ghostPrivacyCutRatioForView(view)));
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
    sourceX: number;
    sourceY: number;
    sourceWidth: number;
    sourceHeight: number;
    destinationX: number;
    destinationY: number;
    destinationWidth: number;
    destinationHeight: number;
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
  drawImage: (
    image: CanvasImageSource,
    sourceX: number,
    sourceY: number,
    sourceWidth: number,
    sourceHeight: number,
    destinationX: number,
    destinationY: number,
    destinationWidth: number,
    destinationHeight: number,
  ) => void;
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
    scale: clamp(transform.scale, minimumScale, maximumScale),
    rotation: clamp(transform.rotation, minimumRotation, maximumRotation),
  };
}

export function ghostPhotoTransformStyle(
  transform: GhostPhotoTransform,
  mirrored = false,
): string {
  const safeTransform = clampGhostPhotoTransform(transform);
  const mirror = mirrored ? "scaleX(-1) " : "";
  return `${mirror}translate(${formatNumber(safeTransform.translateX * 100)}%, ${formatNumber(safeTransform.translateY * 100)}%) rotate(${formatNumber(safeTransform.rotation)}deg) scale(${formatNumber(safeTransform.scale)})`;
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
  transform: GhostPhotoTransform,
): GhostPrivacyLineGeometry {
  const safeTransform = clampGhostPhotoTransform(transform);
  const anchor = transformGhostPoint(
    { x: 0.5, y: ghostPrivacyCutRatioForView(view) },
    safeTransform,
  );
  // The privacy boundary is a horizontal raster crop. Its row follows the
  // transformed neck anchor so the visible line and the encoded crop agree.
  return {
    anchor,
    start: { x: 0, y: anchor.y },
    end: { x: 1, y: anchor.y },
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
  transform: GhostPhotoTransform,
  displaySize: GhostDisplaySize,
  sourceSize: GhostDisplaySize,
): number {
  const line = ghostPrivacyLineGeometry(view, transform);
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
): GhostPhotoRenderPlan {
  if (sourceWidth <= 0 || sourceHeight <= 0) {
    throw new Error("Ghost photo source dimensions must be positive");
  }
  const baseScale = Math.min(
    GHOST_EDITOR_OUTPUT.width / sourceWidth,
    GHOST_EDITOR_OUTPUT.height / sourceHeight,
  );
  const privacyLineDisplayY = Math.round(
    ghostPrivacyLineGeometry(view, transform).anchor.y * GHOST_EDITOR_OUTPUT.height,
  );
  const sourceCropY = Math.round(privacyCropSourceYForView(
    view,
    transform,
    GHOST_EDITOR_OUTPUT,
    { width: sourceWidth, height: sourceHeight },
  ));
  const sourceCropHeight = Math.max(1, sourceHeight - sourceCropY);
  const destinationWidth = sourceWidth * baseScale;
  const destinationHeight = sourceCropHeight * baseScale;
  const privacyCutPixels = Math.round(
    sourceCropY * baseScale,
  );
  return {
    canvasWidth: GHOST_EDITOR_OUTPUT.width,
    canvasHeight: Math.max(1, Math.round(destinationHeight)),
    sourceWidth,
    sourceHeight,
    baseScale,
    sourceCropY,
    privacyCutPixels,
    privacyLineDisplayY,
    draw: {
      sourceX: 0,
      sourceY: sourceCropY,
      sourceWidth,
      sourceHeight: sourceCropHeight,
      destinationX: (GHOST_EDITOR_OUTPUT.width - destinationWidth) / 2,
      destinationY: 0,
      destinationWidth,
      destinationHeight,
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
    context.drawImage(
      image.source,
      plan.draw.sourceX,
      plan.draw.sourceY,
      plan.draw.sourceWidth,
      plan.draw.sourceHeight,
      plan.draw.destinationX,
      plan.draw.destinationY,
      plan.draw.destinationWidth,
      plan.draw.destinationHeight,
    );

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

function transformGhostPoint(point: GhostPoint, transform: GhostPhotoTransform): GhostPoint {
  const radians = transform.rotation * Math.PI / 180;
  const cosine = Math.cos(radians);
  const sine = Math.sin(radians);
  const relativeX = (point.x - 0.5) * transform.scale;
  const relativeY = (point.y - 0.5) * transform.scale;
  return {
    x: 0.5 + relativeX * cosine - relativeY * sine + transform.translateX,
    y: 0.5 + relativeX * sine + relativeY * cosine + transform.translateY,
  };
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
