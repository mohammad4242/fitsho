import { useTranslation } from "react-i18next";

import type { BodyPhotoView } from "./types";

export function GhostOverlayGuide({ view }: { view: BodyPhotoView }) {
  const { t } = useTranslation();
  return (
    <div className="ghost-overlay" aria-label={t("bodyPhotos.camera.overlayLabel")}>
      <div className="ghost-overlay__privacy-cut" aria-label={t("bodyPhotos.camera.privacyCut")}>
        <span>{t("bodyPhotos.camera.privacyCut")}</span>
      </div>
      <div
        className={`ghost-overlay__silhouette ghost-overlay__silhouette--${view}`}
        aria-label={t("bodyPhotos.camera.silhouette", { view: t(`bodyPhotos.views.${view}`) })}
        role="img"
      >
        <svg viewBox="0 0 100 180" aria-hidden="true" focusable="false">
          <path d={silhouettePath(view)} />
        </svg>
      </div>
    </div>
  );
}

function silhouettePath(view: BodyPhotoView): string {
  if (view === "side") {
    return "M46 20 C40 25 40 34 45 39 L42 50 L35 63 L39 91 L34 130 L30 170 L48 170 L53 132 L58 91 L61 64 L55 50 L54 39 C59 33 55 25 46 20 Z";
  }
  if (view === "back") {
    return "M36 20 L28 32 L20 52 L27 62 L32 91 L27 130 L23 170 L40 170 L50 133 L60 170 L77 170 L73 130 L68 91 L73 62 L80 52 L72 32 L64 20 L57 38 L50 44 L43 38 Z";
  }
  return "M36 20 L28 32 L20 52 L28 63 L33 91 L28 130 L24 170 L41 170 L50 133 L59 170 L76 170 L72 130 L67 91 L72 63 L80 52 L72 32 L64 20 L57 38 L50 44 L43 38 Z";
}
