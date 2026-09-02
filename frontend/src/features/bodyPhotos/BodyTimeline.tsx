import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { BeforeAfterSlider } from "./BeforeAfterSlider";
import { ProgressComparison } from "./ProgressComparison";
import { SpecialistReviewStatus } from "./SpecialistReviewStatus";
import type { BodyProgressTimelineItem } from "./types";

export function BodyTimeline({
  items,
  onDelete,
}: {
  items: BodyProgressTimelineItem[];
  onDelete: (session: BodyProgressTimelineItem["session"], trigger: HTMLButtonElement) => void;
}) {
  const { t, i18n } = useTranslation();
  const locale = i18n.resolvedLanguage === "en" ? "en-US" : "fa-IR";
  const incompleteItems = items.filter((item) => item.session.submitted_at === null);
  const analysisItems = items.filter((item) => item.session.submitted_at !== null);

  return (
    <section className="body-timeline" aria-labelledby="body-timeline-title">
      <header className="body-timeline__header">
        <div>
          <p>{t("bodyPhotos.timeline.eyebrow")}</p>
          <h2 id="body-timeline-title">{t("bodyPhotos.timeline.title")}</h2>
        </div>
        <p>{t("bodyPhotos.timeline.intro")}</p>
      </header>

      {incompleteItems.length > 0 && (
        <section className="body-analysis-history body-analysis-incomplete" aria-labelledby="body-timeline-incomplete-title">
          <header>
            <div>
              <p>{t("bodyPhotos.incomplete.eyebrow")}</p>
              <h3 id="body-timeline-incomplete-title">{t("bodyPhotos.incomplete.title")}</h3>
            </div>
          </header>
          <ul aria-label={t("bodyPhotos.incomplete.title")}>
            {incompleteItems.map((item) => (
              <li className="body-analysis-session body-analysis-session--incomplete" key={item.session.id}>
                <div className="body-analysis-session__details">
                  <strong>{formatDate(item.session.created_at, locale)}</strong>
                  <span>{t(`bodyPhotos.status.${item.session.state}`)}</span>
                </div>
                <span>{t("bodyPhotos.timeline.photoCount", { count: item.photos.length })}</span>
                <div className="body-analysis-session__actions">
                  <Link to={`/body-progress/new?sessionId=${item.session.id}`}>{t("bodyPhotos.incomplete.continue")}</Link>
                  <button type="button" onClick={(event) => onDelete(item.session, event.currentTarget)}>
                    {t("bodyPhotos.deleteDialog.deleteUpload")}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {analysisItems.length > 0 && (
        <ol className="body-timeline__list" aria-label={t("bodyPhotos.timeline.title")}>
          {analysisItems.map((item, index) => (
            <TimelineItem item={item} isLatest={index === 0} key={item.session.id} locale={locale} onDelete={onDelete} />
          ))}
        </ol>
      )}
      {analysisItems.length === 0 && incompleteItems.length === 0 && (
        <p className="body-timeline__empty">{t("bodyPhotos.timeline.noAnalyses")}</p>
      )}
    </section>
  );
}

function TimelineItem({
  item,
  isLatest,
  locale,
  onDelete,
}: {
  item: BodyProgressTimelineItem;
  isLatest: boolean;
  locale: string;
  onDelete: (session: BodyProgressTimelineItem["session"], trigger: HTMLButtonElement) => void;
}) {
  const { t } = useTranslation();
  const sessionDate = formatDate(item.session.created_at, locale);
  const comparison = item.comparison;
  return (
    <li className={`body-timeline__item${isLatest ? " body-timeline__item--latest" : ""}`}>
      <article>
        <header className="body-timeline__item-header">
          <div>
            {isLatest && <small>{t("bodyPhotos.timeline.latest")}</small>}
            <time dateTime={item.session.created_at}>{sessionDate}</time>
            <span>{t(`bodyPhotos.status.${item.session.state}`)}</span>
          </div>
          <span>{t("bodyPhotos.timeline.photoCount", { count: item.photos.length })}</span>
        </header>
        {isLatest && item.photos[0] !== undefined && (
          <figure className="body-timeline__latest-photo">
            <img src={item.photos[0].content_url} alt={t("bodyPhotos.timeline.latestPhotoAlt")} />
          </figure>
        )}
        <div className="body-timeline__reviews" aria-label={t("bodyPhotos.timeline.reviewLabel")}>
          <SpecialistReviewStatus review={item.review_state.coach} />
          <SpecialistReviewStatus review={item.review_state.doctor} />
        </div>
        {isLatest && item.snapshot !== null && (
          <section className="body-timeline__snapshot" aria-labelledby={`body-timeline-snapshot-${item.session.id}`}>
            <header>
              <h3 id={`body-timeline-snapshot-${item.session.id}`}>{t("bodyPhotos.timeline.snapshotTitle")}</h3>
              <small>{t("bodyPhotos.timeline.snapshotProvenance")}</small>
            </header>
            <dl>
              <div><dt>{t("bodyPhotos.comparison.measurements.weight_kg")}</dt><dd>{formatValue(item.snapshot.weight_kg, locale)} {t("bodyPhotos.comparison.units.kg")}</dd></div>
              <div><dt>{t("bodyPhotos.comparison.measurements.waist_circumference_cm")}</dt><dd>{formatValue(item.snapshot.waist_circumference_cm, locale)} {t("bodyPhotos.comparison.units.cm")}</dd></div>
              <div><dt>{t("bodyPhotos.comparison.measurements.shoulder_circumference_cm")}</dt><dd>{formatValue(item.snapshot.shoulder_circumference_cm, locale)} {t("bodyPhotos.comparison.units.cm")}</dd></div>
              <div><dt>{t("bodyPhotos.comparison.measurements.hip_circumference_cm")}</dt><dd>{formatValue(item.snapshot.hip_circumference_cm, locale)} {t("bodyPhotos.comparison.units.cm")}</dd></div>
            </dl>
          </section>
        )}
        <div className="body-analysis-session__actions">
          <Link to={`/body-progress/${item.session.id}`}>{t("bodyPhotos.results.viewAnalysis")}</Link>
          <button type="button" onClick={(event) => onDelete(item.session, event.currentTarget)}>
            {t("bodyPhotos.deleteDialog.deleteAnalysis")}
          </button>
        </div>
        {comparison !== null && (
          <>
            <ProgressComparison comparison={comparison} />
            <BeforeAfterSlider
              afterPhotos={comparison.after_photos}
              beforePhotos={comparison.before_photos}
              currentDate={formatDate(comparison.current_session_date, locale)}
              previousDate={formatDate(comparison.previous_session_date, locale)}
            />
          </>
        )}
      </article>
    </li>
  );
}

function formatDate(value: string, locale: string) {
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(new Date(value));
}

function formatValue(value: number, locale: string) {
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(value);
}
