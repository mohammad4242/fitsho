import { useTranslation } from "react-i18next";

import { ghostOverlayAssets, resolveGhostOverlayVariant } from "./ghostOverlayAssets";
import {
  GHOST_EDITOR_DEFAULT_TRANSFORM,
  ghostPercentage,
  ghostPhotoTransformStyle,
  ghostPrivacyLineGeometry,
} from "./ghostPhotoEditor";
import type { Sex } from "../profile/types";
import type { BodyPhotoSide, BodyPhotoView, GhostTransform } from "./types";

export function GhostOverlayGuide({
  sex,
  transform = GHOST_EDITOR_DEFAULT_TRANSFORM,
  sideProfile = "right",
  view,
}: {
  sex?: Sex | null;
  transform?: GhostTransform;
  sideProfile?: BodyPhotoSide;
  view: BodyPhotoView;
}) {
  const { t } = useTranslation();
  const variant = resolveGhostOverlayVariant(sex);
  const mirrored = view === "side" && sideProfile === "left";
  const privacyLine = ghostPrivacyLineGeometry(view, transform, mirrored);
  return (
    <div className="ghost-overlay" aria-label={t("bodyPhotos.camera.overlayLabel")}>
      <div
        className="ghost-overlay__privacy-cut"
        aria-label={t("bodyPhotos.camera.privacyCut")}
        style={{
          top: ghostPercentage(privacyLine.anchor.y),
          left: ghostPercentage(privacyLine.start.x),
          width: ghostPercentage(privacyLine.end.x - privacyLine.start.x),
        }}
      >
        <span>{t("bodyPhotos.camera.privacyCut")}</span>
      </div>
      <div
        className={`ghost-overlay__asset-frame ghost-overlay__asset-frame--${view}`}
        aria-label={t("bodyPhotos.camera.silhouette", { view: t(`bodyPhotos.views.${view}`) })}
        role="img"
        style={{
          transform: ghostPhotoTransformStyle(
            transform,
            mirrored,
          ),
        }}
      >
        <img
          className="ghost-overlay__asset"
          src={ghostOverlayAssets[variant][view]}
          alt=""
          aria-hidden="true"
        />
      </div>
    </div>
  );
}
