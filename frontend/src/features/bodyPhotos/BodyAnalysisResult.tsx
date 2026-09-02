import { useTranslation } from "react-i18next";

import type {
  BodyAnalysis,
  BodyAnalysisClassification,
  BodyAnalysisFinding,
  VisualPhysiqueAssessmentV3,
} from "./types";
import { SpecialistReviewStatus } from "./SpecialistReviewStatus";
import { BodyAnalysisV4Result } from "./BodyAnalysisV4Result";

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
  if (analysis.experience_result !== null && analysis.experience_result !== undefined) {
    return <BodyAnalysisV4Result analysis={analysis} experience={analysis.experience_result} />;
  }
  return <LegacyBodyAnalysisResult analysis={analysis} />;
}

function LegacyBodyAnalysisResult({ analysis }: { analysis: BodyAnalysis }) {
  const { t } = useTranslation();
  const result = analysis.normalized_result;
  if (result === null) return null;

  return (
    <div className="body-analysis-result">
      <section className="body-analysis-stage" aria-labelledby="body-analysis-overview-title">
        <LegacyBodyAreaMap findings={result.findings} />
        <div className="body-analysis-overview"><div><p className="eyebrow eyebrow--accent">{t("bodyPhotos.results.confidenceLabel")}</p><h2 id="body-analysis-overview-title">{formatPercent(result.overall_confidence)}</h2></div><p>{t("bodyPhotos.results.confidenceHelp")}</p></div>
      </section>

      {analysis.unverified_warning && (
        <p className="body-analysis-warning" role="alert">
          {t("bodyPhotos.results.unverifiedWarning")}
        </p>
      )}

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

const legacyAreaCoordinates: Record<BodyAnalysisFinding["body_area"], [number, number]> = {
  shoulders: [100, 58],
  chest: [100, 78],
  back: [100, 84],
  lats: [80, 88],
  arms: [62, 98],
  forearms: [48, 126],
  waist_midsection: [100, 118],
  glutes: [100, 144],
  quads: [82, 172],
  hamstrings: [118, 172],
  calves: [82, 218],
  symmetry: [100, 104],
  visible_alignment_or_posture: [100, 132],
};

function LegacyBodyAreaMap({ findings }: { findings: BodyAnalysisFinding[] }) {
  const { i18n, t } = useTranslation();
  const number = new Intl.NumberFormat(i18n.resolvedLanguage === "en" ? "en-US" : "fa-IR");

  return (
    <section className="body-area-map" aria-label={t("bodyPhotos.results.bodyMapLabel")}>
      <div className="body-area-map__figure" aria-hidden="true">
        <svg viewBox="0 0 200 270" role="presentation">
          <circle className="body-area-map__outline" cx="100" cy="27" r="17" />
          <path className="body-area-map__outline" d="M72 58 Q100 45 128 58 L139 117 Q126 142 121 150 L128 247 M128 72 L153 132 M72 72 L47 132 M72 58 L61 117 Q74 142 79 150 L72 247 M79 150 Q100 161 121 150" />
          <path className="body-area-map__center" d="M100 48V151" />
          {findings.map((finding) => {
            const [cx, cy] = legacyAreaCoordinates[finding.body_area];
            return <circle className="body-area-map__marker" data-classification={finding.classification} cx={cx} cy={cy} r="6" key={finding.body_area} />;
          })}
        </svg>
      </div>
      <div>
        <p className="eyebrow eyebrow--accent">{t("bodyPhotos.results.bodyMapEyebrow")}</p>
        <h2>{t("bodyPhotos.results.bodyMapTitle")}</h2>
        <ul>
          {findings.map((finding) => (
            <li data-classification={finding.classification} key={finding.body_area}>
              <span aria-hidden="true" />
              <div>
                <strong>{t(`bodyPhotos.results.areas.${finding.body_area}`)}</strong>
                <small>{t(`bodyPhotos.results.classifications.${finding.classification}`)}</small>
              </div>
              <b>{number.format(Math.round(finding.confidence * 100))}%</b>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
