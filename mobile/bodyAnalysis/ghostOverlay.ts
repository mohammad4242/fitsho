import { clampGhostScale } from "@fitician/core/body-ghost";
import type { GhostOverlayVariant } from "@fitician/core/body-ghost";
import type { GhostPrivacyLine } from "@fitician/core/body-ghost";
import type { BodyPhotoSide, BodyPhotoView } from "@fitician/core/body-photos";
import type { Sex } from "@fitician/core/profile";

import { bodyPhotoPrivacyLine } from "./privacyCrop";

export type { GhostOverlayVariant } from "@fitician/core/body-ghost";

export type GhostAssetCalibration = {
  readonly scale: number;
  readonly translateYRatio: number;
};

const GHOST_ASSET_CALIBRATIONS: Record<
  Exclude<GhostOverlayVariant, "neutral">,
  Record<BodyPhotoView, GhostAssetCalibration>
> = {
  female: {
    back: { scale: 0.94, translateYRatio: -0.11 },
    front: { scale: 0.78, translateYRatio: -0.027 },
    side: { scale: 0.83, translateYRatio: -0.025 },
  },
  male: {
    back: { scale: 0.91, translateYRatio: -0.103 },
    front: { scale: 0.87, translateYRatio: -0.071 },
    side: { scale: 0.88, translateYRatio: -0.063 },
  },
};

export function resolveGhostOverlayVariant(sex: Sex | null | undefined): GhostOverlayVariant {
  if (sex === "male" || sex === "female") return sex;
  return "neutral";
}

export function getGhostAssetCalibration(
  variant: GhostOverlayVariant,
  view: BodyPhotoView,
): GhostAssetCalibration {
  const resolvedVariant = variant === "female" ? "female" : "male";
  return GHOST_ASSET_CALIBRATIONS[resolvedVariant][view];
}

export type GhostOverlayLayout = {
  readonly assetCalibration: GhostAssetCalibration;
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
    assetCalibration: getGhostAssetCalibration(variant, view),
    mirrored,
    privacyLine: bodyPhotoPrivacyLine(view, scale, mirrored, variant),
    scale,
    view,
  };
}
