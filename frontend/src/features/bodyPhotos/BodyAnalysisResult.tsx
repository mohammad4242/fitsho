import { useTranslation } from "react-i18next";

import type {
  BodyAnalysis,
  BodyAnalysisClassification,
  BodyAnalysisFinding,
  VisualPhysiqueAssessmentV3,
} from "./types";
import { SpecialistReviewStatus } from "./SpecialistReviewStatus";
import { BodyAreaMap } from "./BodyAreaMap";

const findingGroups: Array<{
  classification: BodyAnalysisClassification;
  tone: "strength" | "attention" | "priority" | "uncertain";
  icon: string;
  translation: string;
}> = [
  { classification: "strength", tone: "strength", icon: "✓", translation: "strengths" },
  { classification: "mild_lag", tone: "attention", icon: "△", translation: "attention" },
  { classification: "clear_lag", tone: "priority", icon: "!", translation: "priority" },
  { classification: "uncertain", tone: "uncertain", icon: "?", translation: "uncertain" },
];

export function BodyAnalysisResult({ analysis }: { analysis: BodyAnalysis }) {
  const { t } = useTranslation();
  const result = analysis.normalized_result;
  if (result === null) return null;

  return (
    <div className="body-analysis-result">
      {analysis.unverified_warning && (
        <p className="body-analysis-warning" role="alert">
          {t("bodyPhotos.results.unverifiedWarning")}
        </p>
      )}

      <section className="body-analysis-overview" aria-labelledby="body-analysis-overview-title">
        <div>
          <p className="eyebrow eyebrow--accent">{t("bodyPhotos.results.confidenceLabel")}</p>
          <h2 id="body-analysis-overview-title">{formatPercent(result.overall_confidence)}</h2>
        </div>
        <p>{t("bodyPhotos.results.confidenceHelp")}</p>
      </section>

      <BodyAreaMap findings={result.findings} />

      {analysis.visual_result !== null && analysis.visual_result !== undefined && (
        <section className="body-analysis-overview" aria-labelledby="body-analysis-coach-title">
          <div>
            <p className="eyebrow eyebrow--accent">{t("bodyPhotos.results.coachAssessment")}</p>
            <h2 id="body-analysis-coach-title">
              {t(`bodyPhotos.results.assessmentStatus.${analysis.visual_result.assessment_status}`)}
            </h2>
          </div>
          <p>{analysis.visual_result.overall_assessment.summary_fa}</p>
          <p className="body-photo-muted">{analysis.visual_result.provisional_notice_fa}</p>
        </section>
      )}

      {isV3Checklist(analysis.visual_result) && (
        <ChecklistAssessment assessment={analysis.visual_result} />
      )}

      <section className="body-analysis-reviews" aria-labelledby="body-analysis-reviews-title">
        <h2 id="body-analysis-reviews-title">{t("bodyPhotos.results.reviewTitle")}</h2>
        <div>
          <SpecialistReviewStatus review={analysis.coach_review} />
          <SpecialistReviewStatus review={analysis.doctor_review} />
        </div>
      </section>

      <div className="body-analysis-groups">
        {findingGroups.map((group) => (
          <FindingGroup
            key={group.classification}
            title={t(`bodyPhotos.results.groups.${group.translation}`)}
            tone={group.tone}
            icon={group.icon}
            findings={result.findings.filter(
              (finding) => finding.classification === group.classification,
            )}
          />
        ))}
      </div>

      <aside className="body-analysis-disclaimer">
        <strong>{t("bodyPhotos.results.visibleOnlyTitle")}</strong>
        <p>{t("bodyPhotos.results.visibleOnlyBody")}</p>
      </aside>
    </div>
  );
}

function ChecklistAssessment({ assessment }: { assessment: VisualPhysiqueAssessmentV3 }) {
  const { t } = useTranslation();
  return (
    <>
      <section className="body-goal-suggestion" aria-labelledby="body-goal-suggestion-title">
        <div className="body-goal-suggestion__badge" aria-hidden="true">✦</div>
        <div>
          <p className="eyebrow eyebrow--accent">{t("bodyPhotos.results.goalSuggestionEyebrow")}</p>
          <h2 id="body-goal-suggestion-title">
            {t(`bodyPhotos.results.suggestedGoals.${assessment.goal_suggestion.suggested_goal}`)}
          </h2>
          <p>{assessment.goal_suggestion.reasoning_fa}</p>
          {assessment.goal_suggestion.inputs_unavailable_fa.length > 0 && (
            <p className="body-photo-muted">
              {t("bodyPhotos.results.missingInputs")}: {assessment.goal_suggestion.inputs_unavailable_fa.join(" · ")}
            </p>
          )}
        </div>
      </section>

      <section className="body-checklist" aria-labelledby="body-checklist-title">
        <header>
          <div>
            <p className="eyebrow eyebrow--accent">{t("bodyPhotos.results.checklistEyebrow")}</p>
            <h2 id="body-checklist-title">{t("bodyPhotos.results.checklistTitle")}</h2>
          </div>
          <p>{t("bodyPhotos.results.checklistHelp")}</p>
        </header>
        <div className="body-checklist__list">
          {assessment.findings.map((finding) => (
            <article className="body-checklist__area" key={finding.area}>
              <header>
                <div>
                  <h3>{t(`bodyPhotos.results.areas.${finding.area}`)}</h3>
                  <p>{finding.overall_summary_fa}</p>
                </div>
                <span data-rating={finding.overall_rating}>
                  {t(`bodyPhotos.results.ratings.${finding.overall_rating}`)}
                </span>
              </header>
              <dl>
                {(["front", "side", "back"] as const).map((view) => (
                  <div key={view}>
                    <dt>{t(`bodyPhotos.views.${view}`)}</dt>
                    <dd data-rating={finding[view].rating}>
                      <strong>{t(`bodyPhotos.results.ratings.${finding[view].rating}`)}</strong>
                      <span>{finding[view].evidence_fa}</span>
                    </dd>
                  </div>
                ))}
              </dl>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}

function isV3Checklist(
  assessment: BodyAnalysis["visual_result"],
): assessment is VisualPhysiqueAssessmentV3 {
  return assessment !== null && assessment !== undefined && "goal_suggestion" in assessment;
}

function FindingGroup({
  title,
  tone,
  icon,
  findings,
}: {
  title: string;
  tone: "strength" | "attention" | "priority" | "uncertain";
  icon: string;
  findings: BodyAnalysisFinding[];
}) {
  const { t } = useTranslation();
  return (
    <section className={`body-analysis-group body-analysis-group--${tone}`}>
      <header>
        <span aria-hidden="true">{icon}</span>
        <h2>{title}</h2>
      </header>
      {findings.length === 0 ? (
        <p className="body-photo-muted">{t("bodyPhotos.results.noneInGroup")}</p>
      ) : (
        <ul>
          {findings.map((finding) => (
            <li key={finding.body_area}>
              <div className="body-analysis-finding__heading">
                <strong>{t(`bodyPhotos.results.areas.${finding.body_area}`)}</strong>
                <span>{formatPercent(finding.confidence)}</span>
              </div>
              <p>{finding.explanation}</p>
              {finding.limitations.length > 0 && (
                <div className="body-analysis-limitations">
                  <span>{t("bodyPhotos.results.limitationsLabel")}</span>
                  <ul>
                    {finding.limitations.map((limitation) => (
                      <li key={limitation}>
                        {t(`bodyPhotos.results.limitations.${limitation}`, {
                          defaultValue: formatMachineLabel(limitation),
                        })}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatMachineLabel(value: string): string {
  return value.replaceAll("_", " ");
}
