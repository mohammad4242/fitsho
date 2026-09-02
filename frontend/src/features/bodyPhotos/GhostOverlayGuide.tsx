import { useTranslation } from "react-i18next";

import { ghostOverlayAssets, resolveGhostOverlayVariant } from "./ghostOverlayAssets";
import { ghostPrivacyCutRatioForView } from "./ghostPhotoEditor";
import type { Sex } from "../profile/types";
import type { BodyPhotoSide, BodyPhotoView } from "./types";

export function GhostOverlayGuide({
  sex,
  scale = 1,
  sideProfile = "right",
  view,
}: {
  sex?: Sex | null;
  scale?: number;
  sideProfile?: BodyPhotoSide;
  view: BodyPhotoView;
}) {
  const { t } = useTranslation();
  const variant = resolveGhostOverlayVariant(sex);
  const ghostTransform = view === "side" && sideProfile === "left"
    ? `scaleX(-1) scale(${scale})`
    : `scale(${scale})`;
  return (
    <div className="ghost-overlay" aria-label={t("bodyPhotos.camera.overlayLabel")}>
      <div
        className="ghost-overlay__privacy-cut"
        aria-label={t("bodyPhotos.camera.privacyCut")}
        style={{ top: `${ghostPrivacyCutRatioForView(view) * 100}%` }}
      >
        <span>{t("bodyPhotos.camera.privacyCut")}</span>
      </div>
      <div
        className={`ghost-overlay__asset-frame ghost-overlay__asset-frame--${view}`}
        aria-label={t("bodyPhotos.camera.silhouette", { view: t(`bodyPhotos.views.${view}`) })}
        role="img"
        style={{ transform: ghostTransform }}
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
