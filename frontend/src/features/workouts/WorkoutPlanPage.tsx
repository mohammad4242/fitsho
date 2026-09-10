import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { ApiError } from "../../shared/apiClient";
import { AppIcon, type IconName } from "../../shared/AppIcon";
import { getProfile, updateProfile } from "../profile/api";
import type { WorkoutGenerationMethod } from "../profile/types";
import { ExerciseMedia } from "../exercises/ExerciseMedia";
import {
  downloadWorkoutPlanPdf,
  deleteWorkoutPlan,
  generateWorkoutPlan,
  getActiveWorkoutPlan,
  getWorkoutPlan,
  getWorkoutPlanHistory,
  recordExerciseReplacement,
} from "./api";
import { WeeklyCheckInCard } from "./WeeklyCheckInCard";
import { EndCycleFeedbackCard } from "./EndCycleFeedbackCard";
import { formatPrescriptionTarget } from "./prescriptionFormatter";
import type {
  WorkoutExerciseReplacementReason,
  WorkoutExerciseReplacementScope,
  WorkoutPlan,
  WorkoutPlanExercise,
  WorkoutPlanVersionSummary,
} from "./types";
import "./workoutPlan.css";

type PlanState = "loading" | "empty" | "ready" | "error";
type WorkoutPlanSummaryStatus = "active" | "pending" | "inactive";
type GenerationError =
  | "cooldown"
  | "failed"
  | "bodyweight_level"
  | "bodyweight_days"
  | "bodyweight_pull_up_bar"
  | "bodyweight_exercise";

type DeleteVersionError = { versionId: string; message: string };

const bodyweightGenerationErrors: Record<string, GenerationError> = {
  BODYWEIGHT_ONLY_LEVEL_NOT_SUPPORTED: "bodyweight_level",
  BODYWEIGHT_TEMPLATE_DAYS_NOT_SUPPORTED: "bodyweight_days",
  BODYWEIGHT_PULL_UP_BAR_REQUIRED: "bodyweight_pull_up_bar",
  BODYWEIGHT_TEMPLATE_EXERCISE_UNAVAILABLE: "bodyweight_exercise",
};

const workoutPlanStatusIcons: Record<WorkoutPlanSummaryStatus, IconName> = {
  active: "zap",
  pending: "clock",
  inactive: "lock",
};

const workoutPlanStatusLabels: Record<WorkoutPlanSummaryStatus, string> = {
  active: "workoutPlan.active",
  pending: "workoutPlan.pendingCoach",
  inactive: "workoutPlan.inactive",
};

function getWorkoutPlanSummaryStatus(plan: WorkoutPlan, historical: boolean): WorkoutPlanSummaryStatus {
  if (historical) return "inactive";
  if (plan.status === "pending_review" || plan.coach_review?.state === "pending_coach_review") return "pending";
  return plan.status === "active" ? "active" : "inactive";
}

function generationErrorMessageKey(error: GenerationError): string {
  if (error === "cooldown") return "workoutPlan.generateCooldown";
  if (error === "bodyweight_level") return "workoutPlan.bodyweightLevelUnsupported";
  if (error === "bodyweight_days") return "workoutPlan.bodyweightDaysUnsupported";
  if (error === "bodyweight_pull_up_bar") return "workoutPlan.bodyweightPullUpBarRequired";
  if (error === "bodyweight_exercise") return "workoutPlan.bodyweightExerciseUnavailable";
  return "workoutPlan.generateError";
}

function isDeletableVersion(version: WorkoutPlanVersionSummary): boolean {
  return version.status === "superseded" || version.status === "failed";
}

async function loadMemberPlans() {
  const [activePlan, versions] = await Promise.all([
    getActiveWorkoutPlan(),
    getWorkoutPlanHistory().catch(() => [] as WorkoutPlanVersionSummary[]),
  ]);
  const pendingVersion = versions.find((version) => version.status === "pending_review");
  const pendingPlan = pendingVersion === undefined
    ? null
    : await getWorkoutPlan(pendingVersion.id).catch(() => null);
  return { activePlan, versions, pendingPlan };
}

export function WorkoutPlanPage({ planDurationWeeks }: { planDurationWeeks: number }) {
  const { i18n, t } = useTranslation();
  const [activePlan, setActivePlan] = useState<WorkoutPlan | null>(null);
  const [pendingPlan, setPendingPlan] = useState<WorkoutPlan | null>(null);
  const [selectedHistoricalPlan, setSelectedHistoricalPlan] = useState<WorkoutPlan | null>(null);
  const [history, setHistory] = useState<WorkoutPlanVersionSummary[]>([]);
  const [selectingVersionId, setSelectingVersionId] = useState<string | null>(null);
  const [deletingVersionId, setDeletingVersionId] = useState<string | null>(null);
  const [deleteVersionError, setDeleteVersionError] = useState<DeleteVersionError | null>(null);
  const [state, setState] = useState<PlanState>("loading");
  const [generating, setGenerating] = useState(false);
  const [reused, setReused] = useState(false);
  const [generationError, setGenerationError] = useState<GenerationError | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [generationMethod, setGenerationMethod] = useState<WorkoutGenerationMethod>("fitsho_coach");
  const [savingGenerationMethod, setSavingGenerationMethod] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [pdfError, setPdfError] = useState(false);
  const isEnglish = i18n.resolvedLanguage === "en";
  const l = (fa: string, en: string) => isEnglish ? en : fa;
  const pendingVersionId = history.find((version) => version.status === "pending_review")?.id ?? null;
  const loadedCurrentPlan = pendingVersionId === null
    ? activePlan
    : pendingPlan?.id === pendingVersionId
      ? pendingPlan
      : null;
  const currentPlan = loadedCurrentPlan;
  const displayedPlan = selectedHistoricalPlan ?? currentPlan;
  const isViewingHistorical = selectedHistoricalPlan !== null;
  const displayedPlanDuration = displayedPlan?.plan_duration_weeks ?? planDurationWeeks;
  const hasPendingReview = pendingVersionId !== null;
  const memberHistory = history.filter(
    (version) => version.status !== "pending_review" && version.id !== currentPlan?.id,
  );

  useEffect(() => {
    let active = true;
    setState("loading");
    void loadMemberPlans()
      .then(({ activePlan: loadedActivePlan, versions, pendingPlan: loadedPendingPlan }) => {
        if (!active) return;
        setActivePlan(loadedActivePlan);
        setPendingPlan(loadedPendingPlan);
        setHistory(versions);
        setState(loadedActivePlan === null && loadedPendingPlan === null ? "empty" : "ready");
      })
      .catch(() => {
        if (active) setState("error");
      });
    return () => {
      active = false;
    };
  }, [loadAttempt]);

  useEffect(() => {
    void getProfile().then((profile) => {
      if (profile !== null) setGenerationMethod(profile.workout_generation_method ?? "fitsho_coach");
    }).catch(() => undefined);
  }, []);

  function changeGenerationMethod(method: WorkoutGenerationMethod) {
    const previous = generationMethod;
    setGenerationMethod(method);
    setSavingGenerationMethod(true);
    void updateProfile({ workout_generation_method: method })
      .catch(() => setGenerationMethod(previous))
      .finally(() => setSavingGenerationMethod(false));
  }

  function generate() {
    setGenerating(true);
    setReused(false);
    setGenerationError(null);
    void generateWorkoutPlan()
      .then(async (result) => {
        setSelectedHistoricalPlan(null);
        setActivePlan(result.plan.status === "active" ? result.plan : null);
        setPendingPlan(result.plan.status === "pending_review" ? result.plan : null);
        setState("ready");
        setReused(result.reused);
        try {
          const {
            activePlan: loadedActivePlan,
            versions,
            pendingPlan: loadedPendingPlan,
          } = await loadMemberPlans();
          setActivePlan(loadedActivePlan);
          setPendingPlan(loadedPendingPlan);
          setHistory(versions);
          setState(loadedActivePlan === null && loadedPendingPlan === null ? "empty" : "ready");
        } catch {
          // The successful generation response is already a valid foreground plan.
        }
      })
      .catch((error: unknown) => {
        const errorKind = error instanceof ApiError && error.status === 429
          ? "cooldown"
          : error instanceof ApiError && error.code !== null
            ? bodyweightGenerationErrors[error.code] ?? "failed"
            : "failed";
        setState(currentPlan === null ? "empty" : "ready");
        setGenerationError(errorKind);
      })
      .finally(() => setGenerating(false));
  }

  function selectVersion(version: WorkoutPlanVersionSummary) {
    if (version.id === currentPlan?.id) {
      setSelectedHistoricalPlan(null);
      return;
    }
    setSelectingVersionId(version.id);
    void getWorkoutPlan(version.id)
      .then((loadedPlan) => {
        setSelectedHistoricalPlan(loadedPlan);
        setGenerationError(null);
      })
      .catch(() => undefined)
      .finally(() => setSelectingVersionId(null));
  }

  function deleteVersion(version: WorkoutPlanVersionSummary) {
    if (!isDeletableVersion(version) || deletingVersionId === version.id) return;
    const confirmed = window.confirm(
      `${l("این نسخه قدیمی برنامه تمرینی حذف شود؟", "Delete this old workout plan version?")}\n\n${l("این نسخه از تاریخچه برنامه‌های شما حذف می‌شود.", "This version will be removed from your workout plan history.")}`,
    );
    if (!confirmed) return;

    const wasViewingDeletedVersion = selectedHistoricalPlan?.id === version.id;
    setDeletingVersionId(version.id);
    setDeleteVersionError(null);
    void deleteWorkoutPlan(version.id)
      .then(async () => {
        const {
          activePlan: loadedActivePlan,
          versions,
          pendingPlan: loadedPendingPlan,
        } = await loadMemberPlans();
        setActivePlan(loadedActivePlan);
        setPendingPlan(loadedPendingPlan);
        setHistory(versions);
        if (wasViewingDeletedVersion) setSelectedHistoricalPlan(null);
        setState(loadedActivePlan === null && loadedPendingPlan === null ? "empty" : "ready");
      })
      .catch(() => {
        setDeleteVersionError({
          versionId: version.id,
          message: l(
            "حذف نسخه قدیمی برنامه انجام نشد؛ دوباره تلاش کن.",
            "The old workout plan version could not be deleted. Please try again.",
          ),
        });
      })
      .finally(() => setDeletingVersionId(null));
  }

  function downloadPdf() {
    if (displayedPlan === null || downloadingPdf) return;
    const planId = displayedPlan.id;
    setDownloadingPdf(true);
    setPdfError(false);
    void downloadWorkoutPlanPdf(planId)
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        try {
          const anchor = document.createElement("a");
          anchor.href = url;
          anchor.download = `fitsho-workout-plan-${planId}.pdf`;
          document.body.append(anchor);
          anchor.click();
          anchor.remove();
        } finally {
          URL.revokeObjectURL(url);
        }
      })
      .catch(() => setPdfError(true))
      .finally(() => setDownloadingPdf(false));
  }

  return (
    <div className="workout-plan-shell fitsho-page">
      <main className="workout-plan-main">
        <div className="workout-plan-controls">
          <section className="workout-generation-method" aria-labelledby="workout-generation-method-title">
            <h2 id="workout-generation-method-title">{t("workoutPlan.generationMethodTitle")}</h2>
            <div className="workout-generation-method__choices" role="group" aria-labelledby="workout-generation-method-title">
              <label>
                <input type="radio" name="workout-generation-method" checked={generationMethod === "fitsho_coach"} disabled={savingGenerationMethod} onChange={() => changeGenerationMethod("fitsho_coach")} />
                <span>{t("workoutPlan.fitshoCoach")}</span>
              </label>
              <label>
                <input type="radio" name="workout-generation-method" checked={generationMethod === "ai"} disabled={savingGenerationMethod} onChange={() => changeGenerationMethod("ai")} />
                <span>{t("workoutPlan.aiOption")}</span>
              </label>
            </div>
          </section>
        {state === "ready" && currentPlan !== null && !isViewingHistorical && (
            <GenerateButton
              generating={generating}
              onClick={generate}
              update
              disabled={generationError === "cooldown"}
            />
          )}
        </div>

        {displayedPlan !== null
          ? <WorkoutPlanOverview plan={displayedPlan} historical={isViewingHistorical} isEnglish={isEnglish} />
          : (
            <header className="workout-plan-hero">
              <div className="workout-plan-hero__content">
                <p className="eyebrow">{t("workoutPlan.eyebrow")}</p>
                <h1 className="fitsho-display">{t("workoutPlan.title")}</h1>
                <p>{t("workoutPlan.intro")}</p>
              </div>
              <div className="workout-plan-duration" aria-label={t("workoutPlan.duration", { count: displayedPlanDuration })}>
                <strong>{displayedPlanDuration}</strong>
                <span>{t("workoutPlan.weeks")}</span>
              </div>
            </header>
          )}

        {state === "loading" && <StatusPanel role="status" message={t("workoutPlan.loading")} />}
        {state === "error" && currentPlan === null && (
          <StatusPanel
            role="alert"
            message={t("workoutPlan.loadError")}
            action={t("common.retry")}
            onAction={() => setLoadAttempt((attempt) => attempt + 1)}
          />
        )}
        {state === "empty" && (
          <>
            {generationError !== null && (
              <StatusPanel
                role="alert"
                message={t(generationErrorMessageKey(generationError))}
                action={generationError === "failed" ? t("common.retry") : undefined}
                onAction={generationError === "failed" ? generate : undefined}
              />
            )}
            {hasPendingReview ? (
              <StatusPanel role="status" message={t("workoutPlan.loading")} />
            ) : (
              <section className="workout-empty" aria-labelledby="workout-empty-title">
                <h2 id="workout-empty-title" className="fitsho-display">{t("workoutPlan.emptyTitle")}</h2>
                <p>{t("workoutPlan.emptyBody")}</p>
                <GenerateButton
                  generating={generating}
                  onClick={generate}
                  disabled={generationError === "cooldown"}
                />
              </section>
            )}
          </>
        )}
        {state === "ready" && displayedPlan !== null && (
          <>
            <section className="workout-schedule" aria-labelledby="workout-schedule-title">
              <div className="workout-schedule__heading">
                <div>
                  <p className="eyebrow eyebrow--accent">{t("workoutPlan.weekly")}</p>
                  <h2 id="workout-schedule-title" className="fitsho-display">{t("workoutPlan.scheduleTitle")}</h2>
                </div>
              </div>
              {generating && <p className="workout-generating" role="status">{t("workoutPlan.generating")}</p>}
              <WorkoutDays plan={displayedPlan} isEnglish={isEnglish} titleId="workout-schedule-title" interactive={!isViewingHistorical && displayedPlan.status === "active"} />
            </section>
            <div className="workout-plan-statuses">
              {reused && <p className="workout-reused" role="status">{t("workoutPlan.reused")}</p>}
              {displayedPlan.ai_coach_program_explanation_fa && (
                <aside className="workout-ai-coach" aria-label={t("workoutPlan.aiCoach")}>
                  <span className="workout-ai-coach__icon" aria-hidden="true">✦</span>
                  <div><p>{t("workoutPlan.aiCoach")}</p><strong>{displayedPlan.ai_coach_program_explanation_fa}</strong></div>
                </aside>
              )}
              {displayedPlan.is_stale && <p className="workout-stale" role="status">{t("workoutPlan.stale")}</p>}
              {displayedPlan.warnings?.includes("SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE") && <p className="workout-body-analysis-warning" role="alert">{t("workoutPlan.corePreservationDurationWarning")}</p>}
              {displayedPlan.body_analysis_provenance?.provisional === true && <p className="workout-body-analysis-warning" role="alert">{t("workoutPlan.provisionalBodyAnalysisWarning")}</p>}
              {generationError && <StatusPanel role="alert" message={t(generationErrorMessageKey(generationError))} action={generationError === "failed" ? t("common.retry") : undefined} onAction={generationError === "failed" ? generate : undefined} />}
            </div>
            {!isViewingHistorical && displayedPlan.status === "active" && <WeeklyCheckInCard plan={displayedPlan} />}
          </>
        )}
        <section className="workout-tools" aria-labelledby="workout-future-title">
          <h2 id="workout-future-title">{t("workoutPlan.futureTitle")}</h2>
          <div
            className={`workout-quick-actions${displayedPlan !== null ? " workout-quick-actions--with-feedback" : ""}`}
            role="group"
            aria-labelledby="workout-future-title"
          >
            <button
              className="workout-quick-action"
              type="button"
              disabled={displayedPlan === null || downloadingPdf}
              aria-busy={downloadingPdf}
              aria-label={t("workoutPlan.pdf.title")}
              onClick={downloadPdf}
            >
              <AppIcon name="document" />
              <strong>{t("workoutPlan.pdf.title")}</strong>
              <small>{t(downloadingPdf ? "workoutPlan.pdf.loading" : "workoutPlan.pdf.body")}</small>
            </button>
            {state !== "loading" && displayedPlan !== null && (
              <EndCycleFeedbackCard
                planDurationWeeks={displayedPlan.plan_duration_weeks}
                awaitingCoachApproval={displayedPlan.status === "pending_review"}
              />
            )}
            <Link className="workout-quick-action" aria-label={t("workoutPlan.body.title")} to="/body-progress">
              <AppIcon name="progress" />
              <strong>{t("workoutPlan.body.title")}</strong>
            </Link>
          </div>
          {pdfError && <StatusPanel role="alert" message={t("workoutPlan.pdf.error")} />}
        </section>

        <details className="workout-secondary">
          <summary>{l("جزئیات و تنظیمات برنامه", "Plan details and settings")}</summary>
          <div className="workout-secondary__content">
            <FixedGuidance />
            {displayedPlan?.ai_coach_program_explanation_fa && (
              <aside className="workout-ai-coach" aria-label={t("workoutPlan.aiCoach")}>
                <span className="workout-ai-coach__icon" aria-hidden="true">✦</span>
                <div><p>{t("workoutPlan.aiCoach")}</p><strong>{displayedPlan.ai_coach_program_explanation_fa}</strong></div>
              </aside>
            )}
            {(memberHistory.length > 0 || isViewingHistorical) && (
              <section className="workout-version-history" aria-labelledby="workout-version-history-title">
                <div><p className="eyebrow eyebrow--accent">{l("نسخه‌های برنامه", "Plan versions")}</p><h2 id="workout-version-history-title">{l("تاریخچه برنامه", "Plan history")}</h2></div>
                {isViewingHistorical && <button type="button" onClick={() => setSelectedHistoricalPlan(null)}>{l("بازگشت به برنامه فعلی", "Return to current plan")}</button>}
                <div className="workout-version-history__list">
                  {memberHistory.map((version) => {
                    const label = version.coach_review.state === "coach_approved"
                      ? l("نسخه تأیید مربی", "Coach-approved version")
                      : version.coach_review.state === "coach_rejected"
                        ? l("نسخه برگشت‌داده‌شده برای اصلاح", "Returned for correction")
                        : l("نسخه اولیه", "Initial version");
                    const canDelete = isDeletableVersion(version);
                    return (
                      <div className="workout-version-history__item" key={version.id}>
                        <button
                          type="button"
                          className={`workout-version-history__select${version.id === selectedHistoricalPlan?.id ? " workout-version-history__active" : ""}`}
                          disabled={selectingVersionId !== null}
                          aria-label={`${label} — ${new Intl.DateTimeFormat(isEnglish ? "en" : "fa-IR", { dateStyle: "medium" }).format(new Date(version.created_at))}`}
                          onClick={() => selectVersion(version)}
                        >
                          <strong>{label}</strong>
                          <span>{version.is_active ? l("فعال", "Active") : l("آرشیو", "Archived")}</span>
                        </button>
                        {canDelete && (
                          <button
                            type="button"
                            className="workout-version-history__delete"
                            aria-label={l("حذف نسخه قدیمی برنامه", "Delete old plan version")}
                            disabled={deletingVersionId === version.id}
                            aria-busy={deletingVersionId === version.id}
                            onClick={() => deleteVersion(version)}
                          >
                            <span aria-hidden="true">{l("حذف", "Delete")}</span>
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
                {deleteVersionError !== null && (
                  <StatusPanel
                    role="alert"
                    message={deleteVersionError.message}
                    action={l("تلاش دوباره", "Retry")}
                    onAction={() => {
                      const version = memberHistory.find((item) => item.id === deleteVersionError.versionId);
                      if (version !== undefined) deleteVersion(version);
                    }}
                  />
                )}
              </section>
            )}
          </div>
        </details>

      </main>
    </div>
  );
}

function WorkoutPlanOverview({
  plan,
  historical,
  isEnglish,
}: {
  plan: WorkoutPlan;
  historical: boolean;
  isEnglish: boolean;
}) {
  const { t } = useTranslation();
  const number = new Intl.NumberFormat(isEnglish ? "en-US" : "fa-IR");
  const summaryStatus = getWorkoutPlanSummaryStatus(plan, historical);
  const durations = plan.days
    .map((day) => day.estimated_duration_minutes)
    .filter((duration): duration is number => duration !== null && duration !== undefined);
  const averageSession = durations.length === 0
    ? null
    : Math.round(durations.reduce((total, duration) => total + duration, 0) / durations.length);
  const l = (fa: string, en: string) => isEnglish ? en : fa;

  return (
    <section className="workout-plan-overview" data-testid={`workout-plan-overview-${plan.id}`}>
      <header className="workout-plan-hero">
        <div className="workout-plan-hero__content">
          <p className="eyebrow">{t("workoutPlan.eyebrow")}</p>
          <h1 className="fitsho-display">{t("workoutPlan.title")}</h1>
          <p>{t("workoutPlan.intro")}</p>
        </div>
        <div className="workout-plan-duration" aria-label={t("workoutPlan.duration", { count: plan.plan_duration_weeks })}>
          <strong>{plan.plan_duration_weeks}</strong>
          <span>{t("workoutPlan.weeks")}</span>
        </div>
      </header>

      <section className="workout-plan-context" aria-label={t("workoutPlan.contextLabel")}>
        <span>
          <small>{t("workoutPlan.currentPlan")}</small>
          <strong className={`workout-plan-context__status workout-plan-context__status--${summaryStatus}`}>
            <AppIcon name={workoutPlanStatusIcons[summaryStatus]} className="workout-plan-context__status-icon" />
            {t(workoutPlanStatusLabels[summaryStatus])}
          </strong>
        </span>
        <span>
          <small>{t("workoutPlan.prePlan")}</small>
          <strong>
            {plan.generation_source === "ai"
              ? t("workoutPlan.aiSource")
              : plan.generation_source === "internal_engine"
                ? t("workoutPlan.internalEngineSource")
                : "—"}
          </strong>
        </span>
        <span>
          <small>{t("workoutPlan.trainingDays")}</small>
          <strong>{t("workoutPlan.daysCount", { count: number.format(plan.days.length) })}</strong>
        </span>
        <span>
          <small>{t("workoutPlan.sessionDuration")}</small>
          <strong>
            {averageSession === null
              ? "—"
              : t("workoutPlan.perSession", { count: number.format(averageSession) })}
          </strong>
        </span>
      </section>

      <CoachReviewBanner plan={plan} isEnglish={isEnglish} historical={historical} />
      {historical && <p className="workout-plan-readonly" role="note">{l("این نسخه فقط برای مشاهده است.", "This version is read-only.")}</p>}
    </section>
  );
}

function CoachReviewBanner({ plan, isEnglish, historical }: { plan: WorkoutPlan; isEnglish: boolean; historical: boolean }) {
  const review = plan.coach_review;
  const l = (fa: string, en: string) => isEnglish ? en : fa;
  if (historical) {
    return <p className="workout-review-banner workout-review-banner--history" role="status">{l("در حال مشاهده نسخه قبلی", "Viewing a previous version")}</p>;
  }
  if (plan.status === "pending_review" || review?.state === "pending_coach_review") {
    return (
      <aside className="workout-review-banner workout-review-banner--pending" role="status">
        <span className="workout-review-indicator" aria-hidden="true" />
        <strong>{l("در انتظار تایید مربی", "Waiting for coach approval")}</strong>
      </aside>
    );
  }
  if (review?.state === "coach_approved") {
    const coach = review.coach_display_name ?? l("مربی فیتشو", "Fitsho coach");
    return (
      <aside className="workout-review-banner workout-review-banner--approved" role="status">
        <span className="workout-review-indicator" aria-hidden="true">✓</span>
        <div>
          <strong>{l(`تأییدشده توسط ${coach}`, `Approved by ${coach}`)}</strong>
          {review.approved_at && <time dateTime={review.approved_at}>{new Intl.DateTimeFormat(isEnglish ? "en" : "fa-IR", { dateStyle: "long" }).format(new Date(review.approved_at))}</time>}
          {review.coach_note && <p>{review.coach_note}</p>}
        </div>
      </aside>
    );
  }
  if (review?.state === "coach_rejected") {
    return (
      <aside className="workout-review-banner workout-review-banner--pending" role="status">
        <span className="workout-review-indicator" aria-hidden="true">!</span>
        <div>
          <strong>{l("نیاز به اصلاح طبق نظر مربی", "Returned for coach corrections")}</strong>
          {review.coach_note && <p>{review.coach_note}</p>}
        </div>
      </aside>
    );
  }
  return (
    <aside className="workout-review-banner workout-review-banner--approved" role="status">
      <span className="workout-review-indicator" aria-hidden="true">✓</span>
      <strong>{l("برنامه آماده اجراست", "Ready to train")}</strong>
    </aside>
  );
}

function WorkoutDays({ plan, isEnglish, titleId, interactive }: { plan: WorkoutPlan; isEnglish: boolean; titleId: string; interactive: boolean }) {
  const { t } = useTranslation();
  const l = (fa: string, en: string) => isEnglish ? en : fa;
  return (
    <div className="workout-days" role="list" aria-labelledby={titleId}>
      {plan.days.map((day, dayIndex) => {
        const mainExercises = day.exercises.filter((item) => item.section !== "core");
        const coreExercises = day.exercises.filter((item) => item.section === "core");
        const leadExercise = mainExercises[0] ?? day.exercises[0];
        const renderExercises = (exercises: WorkoutPlanExercise[]) => (
          <ol>
            {exercises.map((item, itemIndex) => {
              const groupIndices = item.superset_group
                ? exercises.flatMap((candidate, index) => (
                  candidate.superset_group === item.superset_group ? [index] : []
                ))
                : [];
              const isSuperset = groupIndices.length === 2
                && groupIndices[1] === groupIndices[0]! + 1;
              const isSupersetStart = isSuperset && itemIndex === groupIndices[0];
              return (
                <li className={`workout-exercise${isSuperset ? " workout-exercise--superset" : ""}`} key={item.order_index}>
                  <ExerciseMedia
                    path={item.exercise.media_path}
                    name={isEnglish ? item.exercise.name_en : item.exercise.name_fa}
                    mediaType={item.exercise.media_type}
                  />
                  <div className="workout-exercise__content">
                    <div className="workout-exercise__heading">
                      <h4>{isEnglish ? item.exercise.name_en : item.exercise.name_fa}</h4>
                      {isSuperset && <span>{t("workoutPlan.superset")}</span>}
                    </div>
                    {isSupersetStart && (
                      <p className="workout-exercise__superset-instruction">
                        {t("workoutPlan.supersetInstruction")}
                      </p>
                    )}
                    <dl>
                      <div><dt>{t("workoutPlan.sets")}</dt><dd>{item.sets}</dd></div>
                      <div><dt>{item.prescription_mode === "duration" ? t("workoutPlan.durationTarget") : t("workoutPlan.reps")}</dt><dd>{formatPrescriptionTarget(item, isEnglish ? "en" : "fa")}</dd></div>
                      <div><dt>{t("workoutPlan.rest")}</dt><dd>{item.rest_seconds}{t("workoutPlan.seconds")}</dd></div>
                      {item.rir !== null && <div><dt>{t("workoutPlan.rir")}</dt><dd>{item.rir}</dd></div>}
                    </dl>
                    {(isEnglish ? item.notes_en : item.notes_fa) !== null && (
                      <p>{isEnglish ? item.notes_en : item.notes_fa}</p>
                    )}
                    <Link to={`/exercises/${item.exercise.slug}`}>{t("workoutPlan.detail")}</Link>
                    {item.alternatives.length > 0 && (
                      <details className="workout-alternatives">
                        <summary>{t("workoutPlan.alternatives")}</summary>
                        {interactive
                          ? <WorkoutExerciseReplacementFlow item={item} isEnglish={isEnglish} />
                          : <AlternativeLinks item={item} isEnglish={isEnglish} />}
                      </details>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        );
        return (
        <details className={`workout-day${dayIndex === 0 ? " workout-day--focus" : ""}`} key={day.day_number} role="listitem">
          <summary>
            {dayIndex === 0 && leadExercise?.exercise.media_path && <span className="workout-day__media"><ExerciseMedia ambient path={leadExercise.exercise.media_path} name={isEnglish ? leadExercise.exercise.name_en : leadExercise.exercise.name_fa} mediaType={leadExercise.exercise.media_type} /></span>}
            <span>{String(day.day_number).padStart(2, "0")}</span>
            <div>
              {dayIndex === 0 && <small>{l("جلسه بعد", "Next session")}</small>}
              <h3>{isEnglish ? day.title_en : day.title_fa}</h3>
              <p>{dayIndex === 0 && leadExercise ? `${isEnglish ? leadExercise.exercise.name_en : leadExercise.exercise.name_fa} · ` : ""}{t("workoutPlan.sessionMinutes", { count: day.estimated_duration_minutes })}</p>
            </div>
          </summary>
          {day.ai_coach_explanation_fa && (
            <aside className="workout-ai-coach workout-ai-coach--day">
              <span className="workout-ai-coach__icon" aria-hidden="true">✦</span>
              <div><p>{t("workoutPlan.aiCoach")}</p><strong>{day.ai_coach_explanation_fa}</strong></div>
            </aside>
          )}
          {renderExercises(mainExercises)}
          {coreExercises.length > 0 && (
            <section className="workout-day__section" aria-labelledby={`workout-day-${day.day_number}-core-title`}>
              <h4 id={`workout-day-${day.day_number}-core-title`}>Core</h4>
              {renderExercises(coreExercises)}
            </section>
          )}
        </details>
        );
      })}
    </div>
  );
}

const replacementReasons: Array<{ value: WorkoutExerciseReplacementReason; fa: string; en: string }> = [
  { value: "equipment_unavailable", fa: "تجهیزاتش را ندارم", en: "I don't have the equipment" },
  { value: "uncomfortable", fa: "با این حرکت راحت نیستم", en: "This movement feels uncomfortable" },
  { value: "pain_or_discomfort", fa: "درد یا ناراحتی دارم", en: "I have pain or discomfort" },
  { value: "temporary_unavailable", fa: "فعلاً دستگاه/محل در دسترس نیست", en: "The equipment or place is temporarily unavailable" },
  { value: "dislike", fa: "این حرکت را دوست ندارم", en: "I don't like this movement" },
  { value: "other", fa: "دلیل دیگر", en: "Another reason" },
];

const replacementScopes: Array<{ value: WorkoutExerciseReplacementScope; fa: string; en: string }> = [
  { value: "this_time", fa: "فقط همین بار", en: "Just this time" },
  { value: "persistent", fa: "از این به بعد", en: "From now on" },
];

function AlternativeLinks({ item, isEnglish }: { item: WorkoutPlanExercise; isEnglish: boolean }) {
  return (
    <ul>
      {item.alternatives.map((alternative) => (
        <li key={alternative.exercise.id}>
          <Link to={`/exercises/${alternative.exercise.slug}`}>
            {isEnglish ? alternative.exercise.name_en : alternative.exercise.name_fa}
          </Link>
          <span>{isEnglish ? alternative.reason_en : alternative.reason_fa}</span>
        </li>
      ))}
    </ul>
  );
}

function WorkoutExerciseReplacementFlow({ item, isEnglish }: { item: WorkoutPlanExercise; isEnglish: boolean }) {
  const [reason, setReason] = useState<WorkoutExerciseReplacementReason | null>(null);
  const [alternativeId, setAlternativeId] = useState<string | null>(null);
  const [step, setStep] = useState<"reason" | "alternative" | "scope" | "success">("reason");
  const [error, setError] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const l = (fa: string, en: string) => isEnglish ? en : fa;
  const selectedAlternative = item.alternatives.find(({ exercise }) => exercise.id === alternativeId)?.exercise;

  function chooseReason(value: WorkoutExerciseReplacementReason) {
    setReason(value);
    setAlternativeId(null);
    setError(false);
    setStep("alternative");
  }

  function chooseAlternative(value: string) {
    setAlternativeId(value);
    setError(false);
    setStep("scope");
  }

  function submit(selectedScope: WorkoutExerciseReplacementScope) {
    if (reason === null || alternativeId === null) return;
    setError(false);
    setSubmitting(true);
    void recordExerciseReplacement({
      workout_plan_exercise_id: item.id,
      replacement_exercise_id: alternativeId,
      reason,
      scope: selectedScope,
    })
      .then(() => setStep("success"))
      .catch(() => {
        setError(true);
        setStep("scope");
      })
      .finally(() => setSubmitting(false));
  }

  if (step === "success" && selectedAlternative !== undefined) {
    return (
      <p className="workout-replacement-success" role="status">
        {l("جایگزین انتخاب‌شده", "Selected replacement")}: {isEnglish ? selectedAlternative.name_en : selectedAlternative.name_fa}
      </p>
    );
  }

  return (
    <div className="workout-replacement-flow">
      {step === "reason" && <p>{l("اول دلیل تعویض را انتخاب کن.", "First, choose why you want to replace it.")}</p>}
      {error && <p className="workout-replacement-error" role="alert">{l("ثبت جایگزین انجام نشد؛ دوباره تلاش کن.", "The replacement could not be saved. Try again.")}</p>}
      {step === "reason" && (
        <div className="workout-replacement-options" role="group" aria-label={l("دلیل تعویض", "Replacement reason")}>
          {replacementReasons.map((option) => (
            <button type="button" key={option.value} onClick={() => chooseReason(option.value)}>
              {l(option.fa, option.en)}
            </button>
          ))}
        </div>
      )}
      {step === "alternative" && (
        <>
          <p>{l("حالا یک حرکت امن از فهرست زیر انتخاب کن.", "Now choose a safe movement from the list below.")}</p>
          <div className="workout-replacement-options" role="group" aria-label={l("حرکت‌های جایگزین امن", "Safe alternatives")}>
            {item.alternatives.map((alternative) => (
              <button
                type="button"
                key={alternative.exercise.id}
                aria-label={isEnglish ? alternative.exercise.name_en : alternative.exercise.name_fa}
                onClick={() => chooseAlternative(alternative.exercise.id)}
              >
                {isEnglish ? alternative.exercise.name_en : alternative.exercise.name_fa}
                <span>{isEnglish ? alternative.reason_en : alternative.reason_fa}</span>
              </button>
            ))}
          </div>
        </>
      )}
      {step === "scope" && selectedAlternative !== undefined && (
        <>
          <p>{l(`برای «${selectedAlternative.name_fa}» این تعویض تا چه زمانی باشد؟`, `How long should “${selectedAlternative.name_en}” replace this movement?`)}</p>
          <div className="workout-replacement-options" role="group" aria-label={l("مدت جایگزینی", "Replacement scope")}>
            {replacementScopes.map((option) => (
              <button type="button" key={option.value} disabled={submitting} onClick={() => submit(option.value)}>
                {l(option.fa, option.en)}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function FixedGuidance() {
  const { t } = useTranslation();
  return (
    <aside className="workout-guidance" aria-labelledby="workout-guidance-title">
      <div><span aria-hidden="true">↗</span><h2 id="workout-guidance-title">{t("workoutPlan.beforeStart")}</h2></div>
      <ul>
        {(["form", "warmup", "progress", "recovery", "pain"] as const).map((item) => (
          <li key={item}>{t(`workoutPlan.guidance.${item}`)}</li>
        ))}
      </ul>
    </aside>
  );
}

function GenerateButton({ generating, onClick, update = false, disabled = false }: { generating: boolean; onClick: () => void; update?: boolean; disabled?: boolean }) {
  const { t } = useTranslation();
  return <button className="workout-generate" type="button" disabled={generating || disabled} onClick={onClick}>{generating ? t("workoutPlan.generating") : t(update ? "workoutPlan.update" : "workoutPlan.generate")}</button>;
}

function StatusPanel({ role, message, action, onAction }: { role: "status" | "alert"; message: string; action?: string; onAction?: () => void }) {
  return <section className="workout-status" role={role}><p>{message}</p>{action !== undefined && onAction !== undefined && <button type="button" onClick={onAction}>{action}</button>}</section>;
}
