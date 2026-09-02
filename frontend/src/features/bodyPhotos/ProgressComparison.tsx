import { useId } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

import type {
  BodyAnalysisClassification,
  BodyProgressComparison,
  BodyProgressMeasurementDelta,
  BodyProgressProvenance,
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
        {isV2 ? (
          <p>{t("bodyPhotos.comparison.interval", {
            previous: formatDate(normalized.previous_session_date, locale),
            current: formatDate(normalized.current_session_date, locale),
            days: normalized.interval_days,
          })}</p>
        ) : (
          <p>{t("bodyPhotos.comparison.disclaimer")}</p>
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
  const visualId = useId();
  const prioritiesId = useId();
  return (
    <>
      <section className="body-progress-comparison__group" aria-labelledby={measurementsId}>
        <header>
          <p className="eyebrow eyebrow--accent">{t("bodyPhotos.comparison.measurementsEyebrow")}</p>
          <h3 id={measurementsId}>{t("bodyPhotos.comparison.measurementsTitle")}</h3>
          <p>{t("bodyPhotos.comparison.measurementNotice")}</p>
        </header>
        <ul className="body-progress-comparison__measurement-list">
          {comparison.measurement_deltas.map((delta) => (
            <MeasurementDelta key={delta.measurement} delta={delta} locale={locale} />
          ))}
        </ul>
      </section>
      <section className="body-progress-comparison__group" aria-labelledby={visualId}>
        <header>
          <p className="eyebrow eyebrow--accent">{t("bodyPhotos.comparison.visualEyebrow")}</p>
          <h3 id={visualId}>{t("bodyPhotos.comparison.visualTitle")}</h3>
          <p>{t("bodyPhotos.comparison.visualObservationNotice")}</p>
        </header>
        <ul className="body-progress-comparison__visual-list">
          {comparison.visual_transitions.map((transition) => (
            <VisualTransition key={transition.body_area} transition={transition} />
          ))}
        </ul>
      </section>
      {comparison.persistent_priorities.length > 0 && (
        <section className="body-progress-comparison__priorities" aria-labelledby={prioritiesId}>
          <h3 id={prioritiesId}>{t("bodyPhotos.comparison.prioritiesTitle")}</h3>
          <ul>
            {comparison.persistent_priorities.map((priority) => (
              <li key={priority.body_area}>
                <strong>{t("bodyPhotos.comparison.persistentPriority", {
                  area: t(`bodyPhotos.results.areas.${priority.body_area}`),
                })}</strong>
                <small>{provenancePairLabel(t, priority.provenance.previous, priority.provenance.current)}</small>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
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
  if (delta.availability !== "exact" || delta.previous === null || delta.current === null || delta.delta === null) {
    return (
      <li className="body-progress-comparison__measurement" data-state="unavailable">
        <strong>{t("bodyPhotos.comparison.measurementUnavailable", { measurement })}</strong>
        <small>{provenancePairLabel(t, delta.provenance.previous, delta.provenance.current)}</small>
      </li>
    );
  }

  return (
    <li className="body-progress-comparison__measurement" data-state="exact">
      <strong>{t("bodyPhotos.comparison.measurementLine", {
        measurement,
        previous: formatNumber(delta.previous, locale),
        current: formatNumber(delta.current, locale),
        delta: formatSignedNumber(delta.delta, locale),
        unit,
      })}</strong>
      <small>{provenancePairLabel(t, delta.provenance.previous, delta.provenance.current)}</small>
    </li>
  );
}

function VisualTransition({ transition }: { transition: BodyProgressVisualTransition }) {
  const { t } = useTranslation();
  return (
    <li className="body-progress-comparison__visual" data-state={transition.state}>
      <strong>{t(`bodyPhotos.results.areas.${transition.body_area}`)}</strong>
      <span>{t(`bodyPhotos.comparison.states.${transition.state}`)}</span>
      <small>{t("bodyPhotos.comparison.visualTransition", {
        previous: classificationLabel(t, transition.previous_classification),
        current: classificationLabel(t, transition.current_classification),
      })}</small>
      <small>{t("bodyPhotos.comparison.visualObservationNotice")}</small>
      {transition.supporting_views.length > 0 && (
        <small>{t("bodyPhotos.comparison.supportingViews", {
          views: transition.supporting_views.map((view) => t(`bodyPhotos.views.${view}`)).join(" · "),
        })}</small>
      )}
      <small>{t("bodyPhotos.comparison.visualReasons", {
        reasons: transition.reason_codes.map((reason) => t(`bodyPhotos.comparison.reasons.${reason}`)).join(" · "),
      })}</small>
      <small>{provenancePairLabel(t, transition.provenance.previous, transition.provenance.current)}</small>
    </li>
  );
}

function LegacyComparison({ comparison }: { comparison: NormalizedBodyProgressComparisonV1 }) {
  const { t } = useTranslation();
  return (
    <>
      <p className="body-progress-comparison__legacy-notice">{t("bodyPhotos.comparison.disclaimer")}</p>
      <ul>
        {comparison.areas.map((area) => (
          <li key={area.body_area} data-state={area.state}>
            <strong>{t(`bodyPhotos.results.areas.${area.body_area}`)}</strong>
            <span>{t(`bodyPhotos.comparison.states.${area.state}`)}</span>
            <small>{t("bodyPhotos.comparison.visualTransition", {
              previous: classificationLabel(t, area.previous_classification),
              current: classificationLabel(t, area.current_classification),
            })}</small>
            <small>{t("bodyPhotos.comparison.visualObservationNotice")}</small>
          </li>
        ))}
      </ul>
    </>
  );
}

function classificationLabel(t: TFunction, classification: BodyAnalysisClassification | null) {
  return classification === null
    ? t("bodyPhotos.comparison.unknown")
    : t(`bodyPhotos.results.classifications.${classification}`);
}

function provenancePairLabel(t: TFunction, previous: BodyProgressProvenance, current: BodyProgressProvenance) {
  return t("bodyPhotos.comparison.provenancePair", {
    previous: provenanceLabel(t, previous),
    current: provenanceLabel(t, current),
  });
}

function provenanceLabel(t: TFunction, provenance: BodyProgressProvenance) {
  return t(`bodyPhotos.comparison.provenance.${provenance.source}`);
}

function formatDate(value: string, locale: string) {
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(new Date(value));
}

function formatNumber(value: number, locale: string) {
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(value);
}

function formatSignedNumber(value: number, locale: string) {
  const formatted = formatNumber(Math.abs(value), locale);
  return value > 0 ? `+${formatted}` : value < 0 ? `-${formatted}` : formatted;
}
