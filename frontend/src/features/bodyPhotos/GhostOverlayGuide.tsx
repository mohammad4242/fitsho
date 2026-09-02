import { useTranslation } from "react-i18next";

import type { BodyPhotoView } from "./types";

export function GhostOverlayGuide({ view }: { view: BodyPhotoView }) {
  const { t } = useTranslation();
  const silhouette = silhouettes[view];
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
          <path className="ghost-overlay__silhouette-fill" d={silhouette.bodyPath} />
          <path className="ghost-overlay__silhouette-outline" d={silhouette.bodyPath} />
          {silhouette.details.map((detail) => (
            <path key={detail} className="ghost-overlay__silhouette-detail" d={detail} />
          ))}
          <path className="ghost-overlay__silhouette-centerline" d={silhouette.centerline} />
        </svg>
      </div>
    </div>
  );
}

type SilhouetteDefinition = {
  bodyPath: string;
  details: readonly [string, string, string];
  centerline: string;
};

const silhouettes: Record<BodyPhotoView, SilhouetteDefinition> = {
  front: {
    bodyPath: "M43 18 C40 23 38 28 36 34 C34 40 30 47 27 56 C28 60 30 63 33 65 C33 74 34 83 36 91 C36 96 34 103 33 110 L28 169 L42 169 L50 126 L58 169 L72 169 L67 110 C66 103 64 96 64 91 C66 83 67 74 67 65 C70 63 72 60 73 56 C70 47 66 40 64 34 C62 28 60 23 57 18 C55 23 53 27 50 31 C47 27 45 23 43 18 Z",
    details: [
      "M36 37 C42 42 58 42 64 37",
      "M37 78 C43 82 57 82 63 78",
      "M36 96 C42 101 58 101 64 96",
    ],
    centerline: "M50 31 C49 57 51 84 50 126",
  },
  side: {
    bodyPath: "M47 18 C43 21 41 27 42 33 C41 39 38 47 34 54 C35 59 38 63 41 65 C42 74 42 84 43 92 C40 101 38 114 36 130 L33 169 L48 169 L53 128 L57 169 L70 169 L64 112 C63 104 61 98 59 93 C61 85 62 76 61 68 C59 61 57 55 57 49 C55 44 54 39 55 34 C58 28 55 21 51 18 C50 24 49 29 47 18 Z",
    details: [
      "M42 40 C47 43 54 43 58 40",
      "M42 79 C48 81 56 80 61 78",
      "M43 96 C49 99 56 99 60 96",
    ],
    centerline: "M50 31 C49 58 51 87 53 128",
  },
  back: {
    bodyPath: "M43 18 C40 23 38 28 36 34 C34 40 30 47 27 56 C28 60 30 63 33 65 C33 74 34 83 36 91 C36 96 34 103 33 110 L28 169 L42 169 L50 126 L58 169 L72 169 L67 110 C66 103 64 96 64 91 C66 83 67 74 67 65 C70 63 72 60 73 56 C70 47 66 40 64 34 C62 28 60 23 57 18 C55 23 53 27 50 31 C47 27 45 23 43 18 Z",
    details: [
      "M36 37 C42 42 58 42 64 37",
      "M37 78 C43 82 57 82 63 78",
      "M36 96 C42 101 58 101 64 96",
    ],
    centerline: "M50 31 C50 57 50 84 50 126",
  },
};
