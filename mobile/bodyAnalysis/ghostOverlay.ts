import {
  clampGhostScale,
  ghostAssetCalibrationForView,
} from "@fitician/core/body-ghost";
import type { GhostOverlayVariant } from "@fitician/core/body-ghost";
import type { GhostPrivacyLine } from "@fitician/core/body-ghost";
import type { BodyPhotoSide, BodyPhotoView } from "@fitician/core/body-photos";
import type { Sex } from "@fitician/core/profile";

import { bodyPhotoPrivacyLine } from "./privacyCrop";

export type { GhostOverlayVariant } from "@fitician/core/body-ghost";

export function resolveGhostOverlayVariant(sex: Sex | null | undefined): GhostOverlayVariant {
  if (sex === "male" || sex === "female") return sex;
  return "neutral";
}

export type GhostOverlayLayout = {
  readonly assetCalibration: ReturnType<typeof ghostAssetCalibrationForView>;
  readonly mirrored: boolean;
  readonly privacyLine: GhostPrivacyLine;
  readonly scale: number;
  readonly view: BodyPhotoView;
};

export function getGhostOverlayLayout(
  view: BodyPhotoView,
  ghostScale = 1,
  sideProfile: BodyPhotoSide = "right",
  variant: GhostOverlayVariant = "male",
): GhostOverlayLayout {
  const scale = clampGhostScale(ghostScale);
  const mirrored = view === "side" && sideProfile === "left";
  return {
    assetCalibration: ghostAssetCalibrationForView(view, variant),
    mirrored,
    privacyLine: bodyPhotoPrivacyLine(view, scale, mirrored, variant),
    scale,
    view,
  };
}
