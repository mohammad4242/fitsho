import { Platform } from "react-native";
import { Images } from "react-native-nitro-image";

import type { GhostOverlayVariant } from "@fitician/core/body-ghost";
import {
  clampGhostPhotoTransform,
  createGhostPhotoRenderPlan,
} from "@fitician/core/body-ghost-editor";
import type {
  GhostPhotoTransform,
} from "@fitician/core/body-ghost-editor";
import type { BodyPhotoView } from "@fitician/core/body-photos";

import { filePathToUri, type BodyPhotoCapturedAsset, type BodyPhotoCaptureSource } from "./cameraCapture";

const ghostCanvasFill = {
  b: 161 / 255,
  g: 163 / 255,
  r: 160 / 255,
} as const;

export type NativeGhostPhotoRenderInput = {
  readonly ghostScale?: number;
  readonly ghostVariant?: GhostOverlayVariant;
  readonly height: number;
  readonly source: BodyPhotoCaptureSource;
  readonly transform: GhostPhotoTransform;
  readonly uri: string;
  readonly view: BodyPhotoView;
  readonly width: number;
};

export async function renderNativeGhostPhoto(
  input: NativeGhostPhotoRenderInput,
): Promise<BodyPhotoCapturedAsset> {
  const source = await Images.loadFromFileAsync(filePathFromUri(input.uri));
  const safeTransform = clampGhostPhotoTransform(input.transform);
  const plan = createGhostPhotoRenderPlan(
    source.width,
    source.height,
    safeTransform,
    input.view,
    input.ghostScale ?? 1,
    input.ghostVariant ?? "male",
  );
  const rotated = safeTransform.rotation === 0
    ? source
    : await source.rotateAsync(safeTransform.rotation);
  const drawWidth = Math.max(1, Math.round(rotated.width * plan.baseScale * safeTransform.scale));
  const drawHeight = Math.max(1, Math.round(rotated.height * plan.baseScale * safeTransform.scale));
  const drawX = Math.round(plan.draw.translateX - drawWidth / 2);
  const drawY = Math.round(plan.draw.translateY - drawHeight / 2);
  const canvas = Images.createBlankImage(
    plan.canvasWidth,
    plan.canvasHeight,
    false,
    ghostCanvasFill,
  );
  const rendered = await canvas.renderIntoAsync(
    rotated,
    drawX,
    drawY,
    ...renderIntoSize(drawX, drawY, drawWidth, drawHeight),
  );
  const outputPath = await rendered.saveToTemporaryFileAsync("jpg", 92);
  if (outputPath.trim().length === 0) throw new Error("Ghost photo output is unavailable");
  return {
    height: plan.canvasHeight,
    mimeType: "image/jpeg",
    privacyCropApplied: true,
    source: input.source,
    uri: filePathToUri(outputPath),
    width: plan.canvasWidth,
  };
}

function filePathFromUri(uri: string): string {
  if (uri.startsWith("file://")) return uri.slice("file://".length);
  if (uri.startsWith("/")) return uri;
  throw new Error("Ghost photo source must be a local file");
}

function renderIntoSize(
  x: number,
  y: number,
  width: number,
  height: number,
): [number, number] {
  if (Platform.OS === "android") {
    // react-native-nitro-image 0.15.2 maps Android's width/height arguments to
    // the destination right/bottom coordinates.
    return [x + width, y + height];
  }
  return [width, height];
}
