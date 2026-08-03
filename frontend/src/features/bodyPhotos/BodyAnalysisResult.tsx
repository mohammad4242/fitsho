import { useTranslation } from "react-i18next";

import type {
  BodyAnalysis,
  BodyAnalysisClassification,
  BodyAnalysisFinding,
} from "./types";
import { SpecialistReviewStatus } from "./SpecialistReviewStatus";

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
