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
        <svg viewBox="0 0 100 180" aria-hidden="true" focusable="false" preserveAspectRatio="xMidYMid meet">
          <path className="ghost-overlay__silhouette-fill" d={silhouette.headPath} />
          <path className="ghost-overlay__silhouette-fill" d={silhouette.bodyPath} />
          <path className="ghost-overlay__silhouette-outline" d={silhouette.headPath} />
          <path className="ghost-overlay__silhouette-outline" d={silhouette.bodyPath} />
          {silhouette.details.map((detail) => (
            <path key={detail} className="ghost-overlay__silhouette-detail" d={detail} />
          ))}
          {silhouette.profilePath !== undefined && (
            <path className="ghost-overlay__silhouette-profile" d={silhouette.profilePath} />
          )}
          <path className="ghost-overlay__silhouette-centerline" d={silhouette.centerline} />
        </svg>
      </div>
    </div>
  );
}

type SilhouetteDefinition = {
  headPath: string;
  bodyPath: string;
  details: readonly [string, string, string];
  profilePath?: string;
  centerline: string;
};

const uprightHeadPath = "M50 9.5 C43.4 9.5 38.6 14.8 38.6 22 C38.6 29.2 43.4 34.1 50 34.1 C56.6 34.1 61.4 29.2 61.4 22 C61.4 14.8 56.6 9.5 50 9.5 Z";
const uprightBodyPath = [
  "M45 31 L45 36 C40 37 36 39 33 43 C31 47 32 56 34 66 L38 88 C39 95 40 101 42.5 107 L43 118 C43 122 46 125 50 125 C54 125 57 122 57 118 L57.5 107 C60 101 61 95 62 88 L66 66 C68 56 69 47 67 43 C64 39 60 37 55 36 L55 31 Z",
  "M34 42 C30.5 43 28.5 46.5 28 51 L26.5 70 C26 78 27 85 29 91 L31 103 C31.5 106 33.5 107.5 35.2 106.5 C36.9 105.5 37.4 103.5 36.8 101 L35 90 C34 83 34 76 35 68 L38 50 C38.8 46 37.5 42.5 34 42 Z",
  "M66 42 C69.5 43 71.5 46.5 72 51 L73.5 70 C74 78 73 85 71 91 L69 103 C68.5 106 66.5 107.5 64.8 106.5 C63.1 105.5 62.6 103.5 63.2 101 L65 90 C66 83 66 76 65 68 L62 50 C61.2 46 62.5 42.5 66 42 Z",
  "M43 116 C42.5 128 41.5 141 40.5 152 L37.5 168 C37 171.2 39 173.3 42 173.3 L46.8 173.3 C48.8 173.3 49.4 171.7 49.1 169.2 L48.2 125 C46.2 123 44.6 120 43 116 Z",
  "M57 116 C57.5 128 58.5 141 59.5 152 L62.5 168 C63 171.2 61 173.3 58 173.3 L53.2 173.3 C51.2 173.3 50.6 171.7 50.9 169.2 L51.8 125 C53.8 123 55.4 120 57 116 Z",
].join(" ");
const sideHeadPath = "M52 9.5 C46.2 9.5 41.7 12.8 40.2 17.4 C39.6 19.3 38.2 20.9 35.3 22.2 L39.6 24.9 C39.9 30.1 43.5 33.7 48.8 34 C54.5 34.3 58.8 29.7 58.8 22.4 C58.8 15.8 55.7 10.2 52 9.5 Z";
const sideBodyPath = [
  "M47.2 31 C47.3 34.4 45 36.8 41.9 38.6 C38.5 40.4 36.4 44.1 36.6 48.1 C36.8 52.8 39.1 57.8 41 62.3 C42.7 66.4 43.3 70.8 42.6 75.2 C41.8 82.6 39.8 89.7 38.1 97.2 C36.4 105.3 35.4 115.4 34.6 125.6 L31.3 167.6 C31 170.7 33 173.2 36 173.2 L43.4 173.2 C45.7 173.2 46.9 171.3 47.2 168.6 L50.1 128 L53.2 168.6 C53.5 171.3 54.7 173.2 57 173.2 L64.5 173.2 C67.5 173.2 69.1 171.2 68.5 168 L64 125.6 C63 115.4 62 105.3 60.4 97.2 C58.8 89.7 57 82.6 57.7 76.3 C58.2 70.6 61.1 66.2 61.5 61.2 C61.9 56.2 59.2 51.8 57.6 47.5 C56.1 43.3 56.6 40.4 54.7 37.5 C52.9 34.8 50.5 32.8 50.2 31 Z",
  "M41.5 41 C38.3 43 37.3 47.2 37.8 52.2 L39.2 68.5 C39.6 72.7 41.3 75.5 43.2 75.3 C45 75.1 45.7 73.1 45.2 70.2 L44 58.5 C43.6 53.5 45.2 48.4 47.8 44.2 L48.6 40.2 Z",
].join(" ");

const silhouettes: Record<BodyPhotoView, SilhouetteDefinition> = {
  front: {
    headPath: uprightHeadPath,
    bodyPath: uprightBodyPath,
    details: [
      "M29.8 50.5 C36.8 46.5 43.4 46 50 50.4 C56.6 46 63.2 46.5 70.2 50.5",
      "M33 77.5 C42 81.5 58 81.5 67 77.5",
      "M36.2 98.5 C43.2 102.5 56.8 102.5 63.8 98.5",
    ],
    centerline: "M50 34 C50 57 50 84 50 127",
  },
  side: {
    headPath: sideHeadPath,
    bodyPath: sideBodyPath,
    details: [
      "M39 45 C43.5 47.3 48.5 47.5 54 45.2 M43.2 47.5 C42.2 56 42.5 66.5 44 74",
      "M42 76 C47.5 79.2 55.5 79.2 60.5 76",
      "M38.2 98 C45 101.5 54.8 101.5 60.8 98",
    ],
    profilePath: "M39.6 24.9 C41.4 25.7 43.1 25.4 44.6 24.2",
    centerline: "M49.8 34 C50.8 57 50.2 85 51.2 127",
  },
  back: {
    headPath: uprightHeadPath,
    bodyPath: uprightBodyPath,
    details: [
      "M29.6 50.5 C36.5 46.3 43.5 46.1 50 49 C56.5 46.1 63.5 46.3 70.4 50.5",
      "M33.5 76 C40.8 79.5 45.5 79.2 50 76.5 C54.5 79.2 59.2 79.5 66.5 76",
      "M36.2 98.5 C42.8 102.2 47.2 102.2 50 99.5 C52.8 102.2 57.2 102.2 63.8 98.5",
    ],
    centerline: "M50 34 C50 57 50 84 50 127",
  },
};
