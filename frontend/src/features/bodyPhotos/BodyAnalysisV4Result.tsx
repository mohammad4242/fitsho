import { useTranslation } from "react-i18next";

import { BodyAreaMap } from "./BodyAreaMap";
import { bodyMapSex } from "./bodyMapRegions";
import { translateExperienceMessage } from "./experienceText";
import { SpecialistReviewStatus } from "./SpecialistReviewStatus";
import type {
  BodyAnalysis,
  BodyAnalysisExperienceDirection,
  BodyAnalysisExperienceIndicator,
  BodyAnalysisExperienceRegion,
  BodyAnalysisExperienceV4,
} from "./types";

const SCORE_ROWS = [
  ["upper_lower_balance", "bodyAnalysis.indicators.upperLowerBalance.title"],
  ["visible_symmetry", "bodyAnalysis.indicators.visibleSymmetry.title"],
  ["body_shape", "bodyAnalysis.indicators.bodyShape.title"],
] as const;

export function BodyAnalysisV4Result({
  analysis,
  experience,
}: {
  analysis: BodyAnalysis;
  experience: BodyAnalysisExperienceV4;
}) {
  const { t } = useTranslation();
  const areaLabel = (area: string) => t(`bodyPhotos.results.areas.${area}`);
  const focusAreas = experience.regions
    .filter((region) => (
      region.display_classification === "primary_priority"
      || region.display_classification === "room_to_grow"
    ))
    .slice(0, 3)
    .map((region) => areaLabel(region.area));
  const firstLook = translateExperienceMessage(t, experience.first_impression, areaLabel);

  return (
    <div className="body-analysis-result body-analysis-result--v4">
      <section className="body-analysis-v4__first-impression" aria-labelledby="body-analysis-v4-first-title">
        <h2 id="body-analysis-v4-first-title">{t("bodyAnalysis.firstImpression.title")}</h2>
        <p>{firstLook}</p>
        <p className="body-analysis-v4__route">{routeText(t, experience.direction, focusAreas)}</p>
      </section>

      <section className="body-analysis-v4__indicators" aria-labelledby="body-analysis-v4-indicators-title">
        <header>
          <h2 id="body-analysis-v4-indicators-title">{t("bodyAnalysis.indicators.title")}</h2>
        </header>
        <div className="body-analysis-v4__score-list" role="list">
          {SCORE_ROWS.map(([key, titleKey]) => (
            <ScoreRow
              indicator={experience.indicators[key]}
              key={key}
              title={t(titleKey)}
            />
          ))}
        </div>
      </section>

      <BodyAreaMap sex={bodyMapSex(experience.input_snapshot.sex)} regions={experience.regions} />

      <section className="body-analysis-v4__summary" aria-label={t("bodyAnalysis.summary.title")}>
        <SummaryCard
          areas={experience.regions.filter((region) => region.display_classification === "primary_priority")}
          areaLabel={areaLabel}
          emptyText={t("bodyAnalysis.summary.noWeaknesses")}
          title={t("bodyAnalysis.summary.weaknesses")}
        />
        <SummaryCard
          areas={experience.regions.filter((region) => region.display_classification === "stronger")}
          areaLabel={areaLabel}
          emptyText={t("bodyAnalysis.summary.noStrengths")}
          title={t("bodyAnalysis.summary.strengths")}
        />
      </section>

      <section className="body-analysis-v4__review-block" aria-labelledby="body-analysis-v4-reviews-title">
        <h2 id="body-analysis-v4-reviews-title">{t("bodyPhotos.results.reviewTitle")}</h2>
        <p className="body-analysis-v4__disclaimer">{t("bodyAnalysis.disclaimer.body")}</p>
        <div className="body-analysis-v4__review-states">
          <SpecialistReviewStatus review={analysis.doctor_review} />
          <SpecialistReviewStatus review={analysis.coach_review} />
        </div>
      </section>
    </div>
  );
}

function ScoreRow({
  indicator,
  title,
}: {
  indicator: BodyAnalysisExperienceIndicator;
  title: string;
}) {
  const score = indicator.score_percent;
  return (
    <div className="body-analysis-v4__score-row" data-testid="body-analysis-score-row" role="listitem">
      <div className="body-analysis-v4__score-heading">
        <strong>{title}</strong>
        <span>{score === null ? "—" : `${score}%`}</span>
      </div>
      <div
        aria-label={title}
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={score ?? undefined}
        className="body-analysis-v4__score-track"
        role="progressbar"
      >
        <span style={{ inlineSize: `${score ?? 0}%` }} />
      </div>
    </div>
  );
}

function SummaryCard({
  areas,
  areaLabel,
  emptyText,
  title,
}: {
  areas: BodyAnalysisExperienceRegion[];
  areaLabel: (area: string) => string;
  emptyText: string;
  title: string;
}) {
  return (
    <article className="body-analysis-v4__summary-card">
      <h2>{title}</h2>
      <p>{areas.length === 0 ? emptyText : areas.map((region) => areaLabel(region.area)).join("، ")}</p>
    </article>
  );
}

function routeText(
  t: (key: string, options?: Record<string, unknown>) => string,
  direction: BodyAnalysisExperienceDirection,
  focusAreas: string[],
): string {
  const reason = direction.reason_codes[0];
  if (reason === "low_body_mass_gain_priority") return t("bodyAnalysis.direction.lowBodyMassRoute");
  if (reason === "high_body_mass_reduction_priority") return t("bodyAnalysis.direction.highBodyMassRoute");

  const goal = direction.goal === null
    ? t("bodyAnalysis.direction.unavailable")
    : t(`bodyAnalysis.direction.goals.${direction.goal}`);
  if (reason === "legacy_goal_requires_confirmation") {
    return t("bodyAnalysis.direction.legacyGoalRoute", { goal });
  }
  if (focusAreas.length === 0) {
    return t("bodyAnalysis.direction.currentGoalRouteWithoutAreas", { goal });
  }
  return t("bodyAnalysis.direction.currentGoalRoute", { goal, areas: focusAreas.join(", ") });
}
