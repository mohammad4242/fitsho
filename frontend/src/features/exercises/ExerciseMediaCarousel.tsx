import { useRef, useState, type PointerEvent } from "react";
import { useTranslation } from "react-i18next";

import { ExerciseMedia } from "./ExerciseMedia";
import type { ExerciseMediaItem } from "./exerciseMediaItems";

const SWIPE_THRESHOLD = 48;
const VIDEO_CONTROLS_HEIGHT = 56;

export function ExerciseMediaCarousel({
  items,
  name,
}: {
  items: ExerciseMediaItem[];
  name: string;
}) {
  const { i18n, t } = useTranslation();
  const [selectedIndex, setSelectedIndex] = useState(0);
  const pointerStart = useRef<{ x: number; y: number; ignore: boolean } | null>(null);
  const selectedItem = items[selectedIndex] ?? items[0];

  if (selectedItem === undefined) return null;

  function handlePointerDown(event: PointerEvent<HTMLDivElement>) {
    const target = event.target as HTMLElement;
    const video = event.currentTarget.querySelector("video");
    const bounds = event.currentTarget.getBoundingClientRect();
    const startedInVideoControls =
      video !== null
      && bounds.height > 0
      && event.clientY >= bounds.bottom - VIDEO_CONTROLS_HEIGHT;
    pointerStart.current = {
      x: event.clientX,
      y: event.clientY,
      ignore: startedInVideoControls || target.closest("select") !== null,
    };
  }

  function handlePointerUp(event: PointerEvent<HTMLDivElement>) {
    const start = pointerStart.current;
    pointerStart.current = null;
    if (start === null || start.ignore) return;

    const deltaX = event.clientX - start.x;
    const deltaY = event.clientY - start.y;
    if (
      Math.abs(deltaX) < SWIPE_THRESHOLD
      || Math.abs(deltaX) <= Math.abs(deltaY) * 1.2
    ) return;

    setSelectedIndex((current) => {
      const next = deltaX < 0 ? current + 1 : current - 1;
      return Math.min(Math.max(next, 0), items.length - 1);
    });
  }

  const formatNumber = (value: number) => new Intl.NumberFormat(i18n.language).format(value);
  const optionLabel = (item: ExerciseMediaItem) =>
    item.presentation === null
      ? t("exerciseDetail.legacyMedia")
      : t(`exerciseDetail.${item.presentation}Video`);

  return (
    <div className="exercise-media-carousel" data-testid="exercise-media-carousel">
      <div
        className="exercise-media-carousel__surface"
        data-testid="exercise-media-surface"
        onPointerCancel={() => { pointerStart.current = null; }}
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
      >
        <ExerciseMedia
          key={selectedItem.key}
          path={selectedItem.media_path}
          name={name}
          mediaType={selectedItem.media_type}
        />
      </div>
      {items.length > 1 && (
        <>
          <span className="exercise-media-carousel__indicator" aria-live="polite">
            {formatNumber(selectedIndex + 1)} / {formatNumber(items.length)}
          </span>
          <label className="exercise-detail-media__selector">
            {t("exerciseDetail.mediaSelector")}
            <select
              aria-label={t("exerciseDetail.mediaSelector")}
              value={selectedItem.key}
              onChange={(event) => {
                const nextIndex = items.findIndex((item) => item.key === event.target.value);
                if (nextIndex >= 0) setSelectedIndex(nextIndex);
              }}
            >
              {items.map((item) => (
                <option key={item.key} value={item.key}>
                  {optionLabel(item)}
                  {item.sort_order !== null && item.sort_order > 0
                    ? ` ${item.sort_order + 1}`
                    : ""}
                </option>
              ))}
            </select>
          </label>
        </>
      )}
      {selectedItem.media_attribution !== null && (
        <small>{selectedItem.media_attribution}</small>
      )}
    </div>
  );
}
