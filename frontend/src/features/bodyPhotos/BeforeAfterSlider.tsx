import { useId, useState } from "react";
import type { CSSProperties, KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";

import type { BodyPhoto, BodyPhotoView } from "./types";

const views: BodyPhotoView[] = ["front", "side", "back"];

export function BeforeAfterSlider({
  beforePhotos,
  afterPhotos,
  previousDate,
  currentDate,
}: {
  beforePhotos: BodyPhoto[];
  afterPhotos: BodyPhoto[];
  previousDate: string;
  currentDate: string;
}) {
  const { t } = useTranslation();
  const componentId = useId();
  const titleId = `${componentId}-title`;
  const stageId = `${componentId}-stage`;
  const [view, setView] = useState<BodyPhotoView>("front");
  const [position, setPosition] = useState(50);
  const beforePhoto = beforePhotos.find((photo) => photo.view === view);
  const afterPhoto = afterPhotos.find((photo) => photo.view === view);
  const viewLabel = t(`bodyPhotos.views.${view}`);

  function handleViewKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const currentIndex = views.indexOf(view);
    const nextIndex = event.key === "ArrowRight"
      ? (currentIndex + 1) % views.length
      : (currentIndex - 1 + views.length) % views.length;
    setView(views[nextIndex] ?? "front");
  }

  function handleSliderKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Home") {
      event.preventDefault();
      setPosition(0);
    } else if (event.key === "End") {
      event.preventDefault();
      setPosition(100);
    } else if (event.key === "ArrowLeft" || event.key === "ArrowDown") {
      event.preventDefault();
      setPosition((current) => Math.max(0, current - 1));
    } else if (event.key === "ArrowRight" || event.key === "ArrowUp") {
      event.preventDefault();
      setPosition((current) => Math.min(100, current + 1));
    }
  }

  return (
    <section className="body-before-after" aria-labelledby={titleId}>
      <header className="body-before-after__header">
        <div>
          <p className="eyebrow eyebrow--accent">{t("bodyPhotos.comparison.beforeAfterEyebrow")}</p>
          <h3 id={titleId}>{t("bodyPhotos.comparison.beforeAfterTitle")}</h3>
        </div>
        <p>{t("bodyPhotos.comparison.visualObservationNotice")}</p>
      </header>
      <div className="body-before-after__views" role="tablist" aria-label={t("bodyPhotos.comparison.beforeAfterViewSelector")}>
        {views.map((nextView) => (
          <button
            aria-selected={view === nextView}
            aria-controls={stageId}
            className="body-before-after__view"
            id={`${componentId}-tab-${nextView}`}
            key={nextView}
            role="tab"
            tabIndex={view === nextView ? 0 : -1}
            type="button"
            onClick={() => setView(nextView)}
            onKeyDown={handleViewKeyDown}
          >
            {t(`bodyPhotos.views.${nextView}`)}
          </button>
        ))}
      </div>
      <div
        aria-labelledby={`${componentId}-tab-${view}`}
        className="body-before-after__stage"
        id={stageId}
        role="tabpanel"
      >
        {beforePhoto !== undefined && afterPhoto !== undefined ? (
          <div
            className="body-before-after__canvas"
            style={{ "--body-before-after-position": `${position}%` } as CSSProperties}
          >
            <figure className="body-before-after__photo body-before-after__photo--before">
              <img src={beforePhoto.content_url} alt={t("bodyPhotos.comparison.beforeAlt", { view: viewLabel })} />
              <figcaption>
                <strong>{t("bodyPhotos.comparison.beforeLabel")}</strong>
                <time dateTime={beforePhoto.created_at}>{previousDate}</time>
              </figcaption>
            </figure>
            <figure className="body-before-after__photo body-before-after__photo--after">
              <img src={afterPhoto.content_url} alt={t("bodyPhotos.comparison.afterAlt", { view: viewLabel })} />
              <figcaption>
                <strong>{t("bodyPhotos.comparison.afterLabel")}</strong>
                <time dateTime={afterPhoto.created_at}>{currentDate}</time>
              </figcaption>
            </figure>
            <div className="body-before-after__divider" aria-hidden="true" />
          </div>
        ) : (
          <p className="body-before-after__empty">{t("bodyPhotos.comparison.viewUnavailable", { view: viewLabel })}</p>
        )}
      </div>
      <label className="body-before-after__control">
        <span>{t("bodyPhotos.comparison.sliderLabel")}</span>
        <input
          aria-label={t("bodyPhotos.comparison.sliderAria")}
          max="100"
          min="0"
          type="range"
          value={position}
          onChange={(event) => setPosition(Number(event.currentTarget.value))}
          onKeyDown={handleSliderKeyDown}
        />
        <span aria-live="polite">{t("bodyPhotos.comparison.sliderPosition", { position })}</span>
      </label>
    </section>
  );
}
