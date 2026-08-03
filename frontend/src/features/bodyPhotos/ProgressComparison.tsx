import { useTranslation } from "react-i18next";

import { compareNormalizedAnalyses, deriveOverallProgressState } from "./comparison";
import type { NormalizedBodyAnalysis } from "./types";

export function ProgressComparison({
  previous,
  current,
}: {
  previous: NormalizedBodyAnalysis;
  current: NormalizedBodyAnalysis;
}) {
  const { t } = useTranslation();
  const comparisons = compareNormalizedAnalyses(previous, current);
  const overallState = deriveOverallProgressState(comparisons);

  return (
    <section className="body-progress-comparison" aria-labelledby="body-progress-comparison-title">
      <header>
        <p className="eyebrow eyebrow--accent">{t("bodyPhotos.comparison.eyebrow")}</p>
        <h2 id="body-progress-comparison-title">{t("bodyPhotos.comparison.title")}</h2>
        <p>{t("bodyPhotos.comparison.disclaimer")}</p>
        <div className="body-progress-overall" data-state={overallState}>
          <span aria-hidden="true">{overallProgressIcon(overallState)}</span>
          <strong>{t(`bodyPhotos.comparison.overall.${overallState}`)}</strong>
        </div>
      </header>
      <ul>
        {comparisons.map((comparison) => (
          <li key={comparison.bodyArea} data-state={comparison.state}>
            <strong>{t(`bodyPhotos.results.areas.${comparison.bodyArea}`)}</strong>
            <span>{t(`bodyPhotos.comparison.states.${comparison.state}`)}</span>
            <small>
              {t("bodyPhotos.comparison.transition", {
                previous: comparison.previousClassification === null
                  ? t("bodyPhotos.comparison.unknown")
                  : t(`bodyPhotos.results.classifications.${comparison.previousClassification}`),
                current: comparison.currentClassification === null
                  ? t("bodyPhotos.comparison.unknown")
                  : t(`bodyPhotos.results.classifications.${comparison.currentClassification}`),
              })}
            </small>
          </li>
        ))}
      </ul>
    </section>
  );
}

function overallProgressIcon(state: "improved" | "stable" | "needs_attention" | "insufficient_data") {
  return { improved: "↗", stable: "→", needs_attention: "↘", insufficient_data: "·" }[state];
}
