import { useTranslation } from "react-i18next";

import { BodyAreaMap } from "./BodyAreaMap";
import { bodyMapSex } from "./bodyMapRegions";
import { translateExperienceMessage } from "./experienceText";
import { SpecialistReviewStatus } from "./SpecialistReviewStatus";
import type {
  BodyAnalysis,
  BodyAnalysisExperienceIndicator,
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
  const directionGoal = experience.direction.goal === null
    ? t("bodyAnalysis.direction.unavailable")
    : t(`bodyAnalysis.direction.goals.${experience.direction.goal}`);
  const reviewNotice = reviewNoticeText(t, experience.review_notice_code);

  return (
    <div className="body-analysis-result body-analysis-result--v4">
      <section className="body-analysis-v4__first-impression" aria-labelledby="body-analysis-v4-first-title">
        <p className="eyebrow eyebrow--accent">{t("bodyAnalysis.firstImpression.eyebrow")}</p>
        <h2 id="body-analysis-v4-first-title">{t("bodyAnalysis.firstImpression.title")}</h2>
        <p>{translateExperienceMessage(t, experience.first_impression, areaLabel)}</p>
        <small>{t(`bodyAnalysis.assessmentStatus.${experience.assessment_status}`)}</small>
      </section>

      <section className="body-analysis-v4__direction" aria-labelledby="body-analysis-v4-direction-title">
        <div>
          <p className="eyebrow eyebrow--accent">{t("bodyAnalysis.direction.eyebrow")}</p>
          <h2 id="body-analysis-v4-direction-title">{t("bodyAnalysis.direction.title")}</h2>
        </div>
        <strong>{t("bodyAnalysis.direction.current", { goal: directionGoal })}</strong>
        <p>
          {experience.direction.status === "aligned_with_current_goal"
            ? t("bodyAnalysis.direction.aligned", { goal: directionGoal })
            : t("bodyAnalysis.direction.confirmationRequired", { goal: directionGoal })}
        </p>
      </section>

      <section className="body-analysis-v4__indicators" aria-labelledby="body-analysis-v4-indicators-title">
        <header>
          <p className="eyebrow eyebrow--accent">{t("bodyAnalysis.indicators.eyebrow")}</p>
          <h2 id="body-analysis-v4-indicators-title">{t("bodyAnalysis.indicators.title")}</h2>
        </header>
        <div className="body-analysis-v4__indicator-grid">
          <IndicatorCard
            indicator={experience.indicators.body_proportion}
            title={t("bodyAnalysis.indicators.bodyProportion.title")}
            text={indicatorText(t, experience.indicators.body_proportion, areaLabel)}
          />
          <IndicatorCard
            indicator={experience.indicators.upper_lower_balance}
            title={t("bodyAnalysis.indicators.upperLowerBalance.title")}
            text={indicatorText(t, experience.indicators.upper_lower_balance, areaLabel)}
          />
          <IndicatorCard
            indicator={experience.indicators.visible_symmetry}
            title={t("bodyAnalysis.indicators.visibleSymmetry.title")}
            text={indicatorText(t, experience.indicators.visible_symmetry, areaLabel)}
          />
          <IndicatorCard
            indicator={experience.indicators.current_development_focus}
            title={t("bodyAnalysis.indicators.currentDevelopmentFocus.title")}
            text={indicatorText(t, experience.indicators.current_development_focus, areaLabel)}
          />
        </div>
      </section>

      <BodyAreaMap sex={bodyMapSex(experience.input_snapshot.sex)} regions={experience.regions} />

      <section className="body-analysis-reviews" aria-labelledby="body-analysis-v4-reviews-title">
        <h2 id="body-analysis-v4-reviews-title">{t("bodyPhotos.results.reviewTitle")}</h2>
        {analysis.unverified_warning && (
          <p className="body-analysis-warning" role="alert">{t("bodyAnalysis.review.provisional")}</p>
        )}
        <p className={`body-analysis-v4__review-notice body-analysis-v4__review-notice--${experience.review_notice_code}`}>
          {reviewNotice}
        </p>
        <div>
          <SpecialistReviewStatus review={analysis.coach_review} />
          <SpecialistReviewStatus review={analysis.doctor_review} />
        </div>
      </section>

      <aside className="body-analysis-disclaimer">
        <strong>{t("bodyAnalysis.disclaimer.title")}</strong>
        <p>{t("bodyAnalysis.disclaimer.body")}</p>
      </aside>
    </div>
  );
}

function IndicatorCard({
  indicator,
  title,
  text,
}: {
  indicator: BodyAnalysisExperienceIndicator;
  title: string;
  text: string;
}) {
  return (
    <article className="body-analysis-v4__indicator" data-status={indicator.status}>
      <span className="body-analysis-v4__indicator-mark" aria-hidden="true" />
      <div>
        <h3>{title}</h3>
        <p>{text}</p>
      </div>
    </article>
  );
}

function indicatorText(
  t: (key: string, options?: Record<string, unknown>) => string,
  indicator: BodyAnalysisExperienceIndicator,
  areaLabel: (area: string) => string,
): string {
  const parameters = {
    ...indicator.parameters,
    state: t(`bodyAnalysis.indicators.states.${indicator.status}`, {
      defaultValue: t("bodyAnalysis.indicators.states.uncertain"),
    }),
  };
  return translateExperienceMessage(t, {
    message_key: indicator.message_key,
    parameters,
  }, areaLabel);
}

function reviewNoticeText(
  t: (key: string, options?: Record<string, unknown>) => string,
  code: string,
): string {
  const key = {
    approved: "bodyAnalysis.review.approved",
    coach_reviewed_doctor_pending: "bodyAnalysis.review.coachReviewedDoctorPending",
    doctor_reviewed_coach_pending: "bodyAnalysis.review.doctorReviewedCoachPending",
    review_pending: "bodyAnalysis.review.pending",
  }[code];
  return t(key ?? "bodyAnalysis.review.pending");
}
