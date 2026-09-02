import { useTranslation } from "react-i18next";

import {
  GHOST_SCALE_MAX,
  GHOST_SCALE_MIN,
  GHOST_SCALE_STEP,
  stepGhostScale,
} from "./ghostScale";

export function GhostScaleControls({
  disabled = false,
  onScaleChange,
  scale,
}: {
  disabled?: boolean;
  onScaleChange: (scale: number) => void;
  scale: number;
}) {
  const { t } = useTranslation();

  return (
    <div className="ghost-scale-controls" role="group" aria-label={t("bodyPhotos.camera.ghostScaleControls")}>
      <span>{t("bodyPhotos.camera.ghostScale", { percent: Math.round(scale * 100) })}</span>
      <div className="ghost-scale-actions">
        <button
          className="secondary-button"
          type="button"
          onClick={() => onScaleChange(stepGhostScale(scale, -GHOST_SCALE_STEP))}
          disabled={disabled || scale <= GHOST_SCALE_MIN}
        >
          {t("bodyPhotos.camera.ghostSmaller")}
        </button>
        <button
          className="secondary-button"
          type="button"
          onClick={() => onScaleChange(stepGhostScale(scale, GHOST_SCALE_STEP))}
          disabled={disabled || scale >= GHOST_SCALE_MAX}
        >
          {t("bodyPhotos.camera.ghostLarger")}
        </button>
      </div>
    </div>
  );
}
