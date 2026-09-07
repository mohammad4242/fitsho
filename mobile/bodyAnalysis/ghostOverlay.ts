import { clampGhostScale } from "@fitician/core/body-ghost";
import type { GhostPrivacyLine } from "@fitician/core/body-ghost";
import type { BodyPhotoSide, BodyPhotoView } from "@fitician/core/body-photos";
import type { Sex } from "@fitician/core/profile";

import { bodyPhotoPrivacyLine } from "./privacyCrop";

export type GhostOverlayVariant = "male" | "female" | "neutral";

export function resolveGhostOverlayVariant(sex: Sex | null | undefined): GhostOverlayVariant {
  if (sex === "male" || sex === "female") return sex;
  return "neutral";
}

export type GhostOverlayLayout = {
  readonly mirrored: boolean;
  readonly privacyLine: GhostPrivacyLine;
  readonly scale: number;
  readonly view: BodyPhotoView;
};

export function getGhostOverlayLayout(
  view: BodyPhotoView,
  ghostScale = 1,
  sideProfile: BodyPhotoSide = "right",
): GhostOverlayLayout {
  const scale = clampGhostScale(ghostScale);
  const mirrored = view === "side" && sideProfile === "left";
  return {
    mirrored,
    privacyLine: bodyPhotoPrivacyLine(view, scale, mirrored),
    scale,
    view,
  };
}
