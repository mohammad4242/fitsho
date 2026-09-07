import { clampGhostScale, ghostPrivacyLineGeometry } from "@fitician/core/body-ghost";
import {
  GHOST_EDITOR_OUTPUT,
  privacyCropSourceYForView,
} from "@fitician/core/body-ghost-editor";
import type { GhostPrivacyLine } from "@fitician/core/body-ghost";
import type { GhostDisplaySize } from "@fitician/core/body-ghost-editor";
import type { BodyPhotoSide, BodyPhotoView } from "@fitician/core/body-photos";

export type BodyPhotoPrivacyCropPlan = {
  readonly displaySize: GhostDisplaySize;
  readonly outputHeight: number;
  readonly outputWidth: number;
  readonly sideProfile: BodyPhotoSide;
  readonly sourceCropY: number;
  readonly sourceSize: GhostDisplaySize;
  readonly view: BodyPhotoView;
  readonly visibleLine: GhostPrivacyLine;
  readonly visibleLineDisplayY: number;
};

export type BodyPhotoPrivacyCropInput = {
  readonly displaySize?: GhostDisplaySize;
  readonly ghostScale?: number;
  readonly sideProfile?: BodyPhotoSide;
  readonly sourceSize: GhostDisplaySize;
  readonly view: BodyPhotoView;
};

export function bodyPhotoPrivacyLine(
  view: BodyPhotoView,
  ghostScale = 1,
  mirrored = false,
): GhostPrivacyLine {
  return ghostPrivacyLineGeometry(view, clampGhostScale(ghostScale), mirrored);
}

export function createBodyPhotoPrivacyCropPlan({
  displaySize = GHOST_EDITOR_OUTPUT,
  ghostScale = 1,
  sideProfile = "right",
  sourceSize,
  view,
}: BodyPhotoPrivacyCropInput): BodyPhotoPrivacyCropPlan {
  assertPositiveSize(displaySize, "display");
  assertPositiveSize(sourceSize, "source");
  const safeScale = clampGhostScale(ghostScale);
  const mirrored = view === "side" && sideProfile === "left";
  const visibleLine = bodyPhotoPrivacyLine(view, safeScale, mirrored);
  const sourceCropY = Math.round(
    privacyCropSourceYForView(view, safeScale, displaySize, sourceSize),
  );
  return {
    displaySize,
    outputHeight: Math.max(1, sourceSize.height - sourceCropY),
    outputWidth: sourceSize.width,
    sideProfile,
    sourceCropY,
    sourceSize,
    view,
    visibleLine,
    visibleLineDisplayY: Math.round(visibleLine.anchor.y * displaySize.height),
  };
}

function assertPositiveSize(size: GhostDisplaySize, label: string): void {
  if (
    !Number.isFinite(size.width)
    || !Number.isFinite(size.height)
    || size.width <= 0
    || size.height <= 0
  ) {
    throw new Error(`${label} dimensions must be positive`);
  }
}
