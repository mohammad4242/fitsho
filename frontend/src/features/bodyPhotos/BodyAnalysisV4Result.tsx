import { useState } from "react";
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

type ActiveTab = "overview" | "muscles" | "progress";

export function BodyAnalysisV4Result({
  analysis,
  experience,
}: {
  analysis: BodyAnalysis;
  experience: BodyAnalysisExperienceV4;
}) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<ActiveTab>("overview");
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

  const tabs: Array<{ id: ActiveTab; label: string; icon: string }> = [
    {
      id: "overview",
      label: t("bodyAnalysis.tabs.overview", { defaultValue: "اسکن و شاخص‌ها" }),
      icon: "M12 2a10 10 0 1 0 10 10A10.011 10.011 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8.009 8.009 0 0 1-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z",
    },
    {
      id: "muscles",
      label: t("bodyAnalysis.tabs.muscles", { defaultValue: "آنالیز عضلات" }),
      icon: "M20.57 14.86L22 13.43 20.57 12 17 15.57 8.43 7 12 3.43 10.57 2 9.14 3.43 7.71 2 5.57 4.14 4.14 2.71 2.71 4.14l1.43 1.43L2 7.71l1.43 1.43L2 10.57 3.43 12 7 8.43 15.57 17 12 20.57 13.43 22l1.43-1.43L16.29 22l2.14-2.14 1.43 1.43 1.43-1.43-1.43-1.43L22 16.29z",
    },
    {
      id: "progress",
      label: t("bodyAnalysis.tabs.progress", { defaultValue: "روند و تخصصی" }),
      icon: "M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6z",
    },
  ];

  return (
    <div className="body-analysis-result body-analysis-result--v4">
      {/* 3-Tab Navigator */}
      <nav className="body-analysis-v4__tabs" role="tablist" aria-label={t("bodyPhotos.results.title")}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            id={`body-tab-${tab.id}`}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            aria-controls={`body-panel-${tab.id}`}
            className={`body-analysis-v4__tab-btn ${activeTab === tab.id ? "body-analysis-v4__tab-btn--active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18" aria-hidden="true">
              <path d={tab.icon} />
            </svg>
            <span>{tab.label}</span>
          </button>
        ))}
      </nav>

      {/* PAGE 1: SCAN OVERVIEW & 3 INDICATORS */}
      <div
        id="body-panel-overview"
        role="tabpanel"
        aria-labelledby="body-tab-overview"
        className={`body-analysis-v4__panel ${activeTab === "overview" ? "body-analysis-v4__panel--active" : "body-analysis-v4__panel--hidden"}`}
        hidden={activeTab !== "overview"}
      >
        <BodyScanOverview
          experience={experience}
          summaryMessage={firstLook}
          routeMessage={route}
        />
        <BodyAnalysisScoreStrip indicators={experience.indicators} />
      </div>

      {/* PAGE 2: INTERACTIVE MUSCLE ANALYSIS */}
      <div
        id="body-panel-muscles"
        role="tabpanel"
        aria-labelledby="body-tab-muscles"
        className={`body-analysis-v4__panel ${activeTab === "muscles" ? "body-analysis-v4__panel--active" : "body-analysis-v4__panel--hidden"}`}
        hidden={activeTab !== "muscles"}
      >
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
      </div>

      {/* PAGE 3: PROGRESS & SPECIALIST REVIEWS */}
      <div
        id="body-panel-progress"
        role="tabpanel"
        aria-labelledby="body-tab-progress"
        className={`body-analysis-v4__panel ${activeTab === "progress" ? "body-analysis-v4__panel--active" : "body-analysis-v4__panel--hidden"}`}
        hidden={activeTab !== "progress"}
      >
        <BodyAnalysisProgressStrip currentSessionId={analysis.session_id} />

        <section className="body-analysis-v4__review-block" aria-labelledby="body-analysis-v4-reviews-title">
          <h2 id="body-analysis-v4-reviews-title">{t("bodyPhotos.results.reviewTitle")}</h2>
          <p className="body-analysis-v4__disclaimer">{t("bodyAnalysis.disclaimer.body")}</p>
          <div className="body-analysis-v4__review-states">
            <SpecialistReviewStatus review={analysis.doctor_review} />
            <SpecialistReviewStatus review={analysis.coach_review} />
          </div>
        </section>
      </div>
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
