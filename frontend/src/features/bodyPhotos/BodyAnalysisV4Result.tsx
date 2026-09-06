import { useTranslation } from "react-i18next";

import { BodyAnalysisProgressStrip } from "./BodyAnalysisProgressStrip";
import { BodyAnalysisScoreStrip } from "./BodyAnalysisScoreStrip";
import { BodyAreaMap } from "./BodyAreaMap";
import { bodyMapSex } from "./bodyMapRegions";
import { BodyScanOverview } from "./BodyScanOverview";
import { translateExperienceMessage } from "./experienceText";
import { SpecialistReviewStatus } from "./SpecialistReviewStatus";
import type {
  BodyAnalysis,
  BodyAnalysisExperienceDirection,
  BodyAnalysisExperienceRegion,
  BodyAnalysisExperienceV4,
} from "./types";

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

  // Up to 3 key weaknesses (primary_priority first, then room_to_grow)
  const keyWeaknesses = [
    ...experience.regions.filter((region) => region.display_classification === "primary_priority"),
    ...experience.regions.filter((region) => region.display_classification === "room_to_grow"),
  ].slice(0, 3);

  // Up to 3 key strengths
  const keyStrengths = experience.regions
    .filter((region) => region.display_classification === "stronger")
    .slice(0, 3);

  const firstLook = translateExperienceMessage(t, experience.first_impression, areaLabel);
  const route = routeText(t, experience.direction, focusAreas);

  return (
    <div className="body-analysis-result body-analysis-result--v4">
      {/* 1. TOP SCAN OVERVIEW */}
      <BodyScanOverview
        experience={experience}
        summaryMessage={firstLook}
        routeMessage={route}
      />

      {/* 2. THREE VISUAL SCORE INDICATORS */}
      <BodyAnalysisScoreStrip indicators={experience.indicators} />

      {/* 3. INTERACTIVE BODY ANALYSIS */}
      <section className="body-analysis-v4__interactive-section" aria-label={t("bodyAnalysis.map.title")}>
        <BodyAreaMap sex={bodyMapSex(experience.input_snapshot.sex)} regions={experience.regions} />

        <div className="body-analysis-v4__summary" aria-label={t("bodyAnalysis.summary.title")}>
          <SummaryCard
            areas={keyWeaknesses}
            areaLabel={areaLabel}
            emptyText={t("bodyAnalysis.summary.noWeaknesses")}
            title={t("bodyAnalysis.summary.weaknesses")}
            tone="priority"
          />
          <SummaryCard
            areas={keyStrengths}
            areaLabel={areaLabel}
            emptyText={t("bodyAnalysis.summary.noStrengths")}
            title={t("bodyAnalysis.summary.strengths")}
            tone="strength"
          />
        </div>
      </section>

      {/* 4. PROGRESS OVER TIME */}
      <BodyAnalysisProgressStrip currentSessionId={analysis.session_id} />

      {/* 5. SPECIALIST REVIEW / DISCLAIMER */}
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

function SummaryCard({
  areas,
  areaLabel,
  emptyText,
  title,
  tone,
}: {
  areas: BodyAnalysisExperienceRegion[];
  areaLabel: (area: string) => string;
  emptyText: string;
  title: string;
  tone: "priority" | "strength";
}) {
  return (
    <article className={`body-analysis-v4__summary-card body-analysis-v4__summary-card--${tone}`}>
      <h2>{title}</h2>
      {areas.length === 0 ? (
        <p>{emptyText}</p>
      ) : (
        <ul className="body-analysis-v4__summary-chips" aria-label={title}>
          {areas.map((region) => (
            <li key={region.area} className="body-analysis-v4__summary-chip">
              <span className="body-analysis-v4__summary-chip-dot" aria-hidden="true" />
              <span>{areaLabel(region.area)}</span>
            </li>
          ))}
        </ul>
      )}
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
