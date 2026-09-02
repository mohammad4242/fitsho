import { useId } from "react";
import { useTranslation } from "react-i18next";

import type {
  BodyArea,
  BodyProgressComparison,
  BodyProgressMeasurementDelta,
  BodyProgressState,
  BodyProgressVisualTransition,
  NormalizedBodyProgressComparisonV1,
  NormalizedBodyProgressComparisonV2,
} from "./types";

export function ProgressComparison({ comparison }: { comparison: BodyProgressComparison }) {
  const { t, i18n } = useTranslation();
  const titleId = useId();
  const normalized = comparison.normalized_result;
  const isV2 = normalized.schema_version === "2.0";
  const locale = i18n.resolvedLanguage === "en" ? "en-US" : "fa-IR";

  return (
    <section className="body-progress-comparison" aria-labelledby={titleId}>
      <header>
        <p className="eyebrow eyebrow--accent">{t("bodyPhotos.comparison.eyebrow")}</p>
        <h2 id={titleId}>{t("bodyPhotos.comparison.title")}</h2>
        {isV2 && (
          <p>{t("bodyPhotos.comparison.interval", {
            previous: formatDate(normalized.previous_session_date, locale),
            current: formatDate(normalized.current_session_date, locale),
            days: normalized.interval_days,
          })}</p>
        )}
      </header>
      {isV2 ? (
        <V2Comparison comparison={normalized} locale={locale} />
      ) : (
        <LegacyComparison comparison={normalized} />
      )}
    </section>
  );
}

function V2Comparison({
  comparison,
  locale,
}: {
  comparison: NormalizedBodyProgressComparisonV2;
  locale: string;
}) {
  const { t } = useTranslation();
  const measurementsId = useId();
  const exactMeasurements = comparison.measurement_deltas.filter(isExactMeasurement);
  const biggestChange = selectBiggestChange(comparison.visual_transitions);

  return (
    <>
      <BiggestChange transition={biggestChange} />
      <section className="body-progress-comparison__group" aria-labelledby={measurementsId}>
        <header>
          <h3 id={measurementsId}>{t("bodyPhotos.comparison.measurementsTitle")}</h3>
        </header>
        {exactMeasurements.length > 0 ? (
          <ul className="body-progress-comparison__measurement-chart">
            {exactMeasurements.map((delta) => (
              <MeasurementDelta
                delta={delta}
                key={delta.measurement}
                locale={locale}
              />
            ))}
          </ul>
        ) : (
          <p className="body-progress-comparison__empty">{t("bodyPhotos.comparison.noMeasurements")}</p>
        )}
      </section>
    </>
  );
}

function BiggestChange({
  transition,
}: {
  transition: { body_area: BodyArea; state: BodyProgressState } | null;
}) {
  const { t } = useTranslation();
  const messageKey = transition?.state === "improved"
    ? "bodyPhotos.comparison.biggestChangePositive"
    : transition?.state === "declined_or_less_balanced"
      ? "bodyPhotos.comparison.biggestChangeNegative"
      : null;

  return (
    <section
      aria-labelledby="body-progress-biggest-change-title"
      className="body-progress-comparison__biggest-change"
      data-state={transition?.state}
    >
      <h3 id="body-progress-biggest-change-title">{t("bodyPhotos.comparison.biggestChangeTitle")}</h3>
      {transition !== null && messageKey !== null ? (
        <div className="body-progress-comparison__biggest-content" data-state={transition.state}>
          <strong>{t(`bodyPhotos.results.areas.${transition.body_area}`)}</strong>
          <p>{t(messageKey)}</p>
        </div>
      ) : (
        <p>{t("bodyPhotos.comparison.biggestChangeNone")}</p>
      )}
    </section>
  );
}

function MeasurementDelta({
  delta,
  locale,
}: {
  delta: BodyProgressMeasurementDelta;
  locale: string;
}) {
  const { t } = useTranslation();
  const measurement = t(`bodyPhotos.comparison.measurements.${delta.measurement}`);
  const unit = t(`bodyPhotos.comparison.units.${delta.unit}`);
  const previous = delta.previous ?? 0;
  const current = delta.current ?? 0;
  const maximum = Math.max(1, previous, current);
  const previousWidth = (previous / maximum) * 100;
  const currentWidth = (current / maximum) * 100;

  return (
    <li className="body-progress-comparison__measurement" data-testid="body-progress-measurement-row">
      <div className="body-progress-comparison__measurement-heading">
        <strong>{measurement}</strong>
        <span>{unit}</span>
      </div>
      <div
        aria-label={t("bodyPhotos.comparison.measurementChartAria", { measurement })}
        className="body-progress-comparison__measurement-bars"
        role="img"
      >
        <span
          className="body-progress-comparison__measurement-bar body-progress-comparison__measurement-bar--previous"
          style={{ inlineSize: `${previousWidth}%` }}
        />
        <span
          className="body-progress-comparison__measurement-bar body-progress-comparison__measurement-bar--current"
          style={{ inlineSize: `${currentWidth}%` }}
        />
      </div>
      <div className="body-progress-comparison__measurement-values">
        <span>
          <i className="body-progress-comparison__legend-dot body-progress-comparison__legend-dot--previous" aria-hidden="true" />
          {t("bodyPhotos.comparison.previousLabel")}: {formatNumber(previous, locale)} {unit}
        </span>
        <span>
          <i className="body-progress-comparison__legend-dot body-progress-comparison__legend-dot--current" aria-hidden="true" />
          {t("bodyPhotos.comparison.currentLabel")}: {formatNumber(current, locale)} {unit}
        </span>
      </div>
    </li>
  );
}

function LegacyComparison({ comparison }: { comparison: NormalizedBodyProgressComparisonV1 }) {
  return <BiggestChange transition={selectBiggestChange(comparison.areas)} />;
}

function isExactMeasurement(delta: BodyProgressMeasurementDelta) {
  return delta.availability === "exact"
    && delta.previous !== null
    && delta.current !== null;
}

function selectBiggestChange(
  transitions: Array<Pick<BodyProgressVisualTransition, "body_area" | "state" | "change_confidence">>
    | NormalizedBodyProgressComparisonV1["areas"],
): { body_area: BodyArea; state: BodyProgressState } | null {
  const meaningful = transitions.filter((transition) => (
    transition.state === "improved" || transition.state === "declined_or_less_balanced"
  ));
  if (meaningful.length === 0) return null;
  const biggest = [...meaningful].sort((left, right) => right.change_confidence - left.change_confidence)[0];
  return biggest === undefined ? null : { body_area: biggest.body_area, state: biggest.state };
}

function formatDate(value: string, locale: string) {
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(new Date(value));
}

function formatNumber(value: number, locale: string) {
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(value);
}
