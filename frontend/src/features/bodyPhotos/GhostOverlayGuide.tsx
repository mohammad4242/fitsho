import { useTranslation } from "react-i18next";

import { ghostOverlayAssets, resolveGhostOverlayVariant } from "./ghostOverlayAssets";
import {
  ghostPercentage,
  ghostGuideTransformStyle,
  ghostPrivacyLineGeometry,
} from "./ghostPhotoEditor";
import type { Sex } from "../profile/types";
import type { BodyPhotoSide, BodyPhotoView } from "./types";

export function GhostOverlayGuide({
  sex,
  ghostScale = 1,
  sideProfile = "right",
  view,
}: {
  sex?: Sex | null;
  ghostScale?: number;
  sideProfile?: BodyPhotoSide;
  view: BodyPhotoView;
}) {
  const { t } = useTranslation();
  const variant = resolveGhostOverlayVariant(sex);
  const mirrored = view === "side" && sideProfile === "left";
  const privacyLine = ghostPrivacyLineGeometry(view, ghostScale, mirrored);
  return (
    <div
      className="ghost-overlay"
      aria-label={t("bodyPhotos.camera.overlayLabel")}
      data-ghost-view={view}
      data-ghost-scale={ghostScale}
      data-ghost-mirrored={mirrored}
    >
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
        className={`ghost-overlay__asset-frame ghost-overlay__asset-frame--${view} ghost-overlay__asset-frame--${variant}`}
        aria-label={t("bodyPhotos.camera.silhouette", { view: t(`bodyPhotos.views.${view}`) })}
        role="img"
        style={{
          transform: ghostGuideTransformStyle(ghostScale, mirrored),
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
