import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { ApiError } from "../../shared/apiClient";
import { getProfile, updateProfile } from "../profile/api";
import type { WorkoutGenerationMethod } from "../profile/types";
import { ExerciseMedia } from "../exercises/ExerciseMedia";
import {
  generateWorkoutPlan,
  getActiveWorkoutPlan,
  getWorkoutPlan,
  getWorkoutPlanHistory,
} from "./api";
import type { WorkoutPlan, WorkoutPlanVersionSummary } from "./types";
import "./workoutPlan.css";

type PlanState = "loading" | "empty" | "ready" | "error";

export function WorkoutPlanPage({ planDurationWeeks }: { planDurationWeeks: number }) {
  const { i18n, t } = useTranslation();
  const [plan, setPlan] = useState<WorkoutPlan | null>(null);
  const [activePlanId, setActivePlanId] = useState<string | null>(null);
  const [history, setHistory] = useState<WorkoutPlanVersionSummary[]>([]);
  const [selectingVersionId, setSelectingVersionId] = useState<string | null>(null);
  const [state, setState] = useState<PlanState>("loading");
  const [generating, setGenerating] = useState(false);
  const [reused, setReused] = useState(false);
  const [generationError, setGenerationError] = useState<"cooldown" | "failed" | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [generationMethod, setGenerationMethod] = useState<WorkoutGenerationMethod>("fitsho_coach");
  const [savingGenerationMethod, setSavingGenerationMethod] = useState(false);
  const isEnglish = i18n.resolvedLanguage === "en";
  const l = (fa: string, en: string) => isEnglish ? en : fa;
  const displayedPlanDuration = plan?.plan_duration_weeks ?? planDurationWeeks;
  const isViewingHistorical = plan !== null && activePlanId !== null && plan.id !== activePlanId;
  const number = new Intl.NumberFormat(isEnglish ? "en-US" : "fa-IR");
  const sessionDurations = plan?.days.map((day) => day.estimated_duration_minutes) ?? [];
  const shortestSession = sessionDurations.length > 0 ? Math.min(...sessionDurations) : null;
  const longestSession = sessionDurations.length > 0 ? Math.max(...sessionDurations) : null;

  useEffect(() => {
    let active = true;
    setState("loading");
    void Promise.all([
      getActiveWorkoutPlan(),
      getWorkoutPlanHistory().catch(() => [] as WorkoutPlanVersionSummary[]),
    ])
      .then(([currentPlan, versions]) => {
        if (!active) return;
        setPlan(currentPlan);
        setActivePlanId(currentPlan?.id ?? null);
        setHistory(versions);
        setState(currentPlan === null ? "empty" : "ready");
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
      .then((result) => {
        setPlan(result.plan);
        setActivePlanId(result.plan.id);
        setState("ready");
        setReused(result.reused);
        void getWorkoutPlanHistory().then(setHistory).catch(() => undefined);
      })
      .catch((error: unknown) => {
        const errorKind = error instanceof ApiError && error.status === 429 ? "cooldown" : "failed";
        setState(plan === null ? "empty" : "ready");
        setGenerationError(errorKind);
      })
      .finally(() => setGenerating(false));
  }

  function selectVersion(version: WorkoutPlanVersionSummary) {
    if (version.id === plan?.id) return;
    setSelectingVersionId(version.id);
    void getWorkoutPlan(version.id)
      .then(setPlan)
      .catch(() => undefined)
      .finally(() => setSelectingVersionId(null));
  }

  return (
    <div className="workout-plan-shell fitsho-page">
      <AuthenticatedHeader />
      <main className="workout-plan-main">
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

        {plan !== null && shortestSession !== null && longestSession !== null && (
          <section className="workout-plan-context" aria-label={t("workoutPlan.contextLabel")}>
            <span><small>{t("workoutPlan.currentPlan")}</small><strong>{t("workoutPlan.active")}</strong></span>
            <span><small>{t("workoutPlan.cycle")}</small><strong>{t("workoutPlan.duration", { count: number.format(displayedPlanDuration) })}</strong></span>
            <span><small>{t("workoutPlan.trainingDays")}</small><strong>{t("workoutPlan.daysCount", { count: number.format(plan.days.length) })}</strong></span>
            <span>
              <small>{t("workoutPlan.sessionDuration")}</small>
              <strong>{shortestSession === longestSession
                ? t("workoutPlan.perSession", { count: number.format(shortestSession) })
                : t("workoutPlan.sessionRange", { min: number.format(shortestSession), max: number.format(longestSession) })}</strong>
            </span>
          </section>
        )}

        <FixedGuidance />

        <section className="workout-generation-method" aria-labelledby="workout-generation-method-title">
          <div>
            <p className="eyebrow eyebrow--accent">{t("workoutPlan.generationMethodEyebrow")}</p>
            <h2 id="workout-generation-method-title">{t("workoutPlan.generationMethodTitle")}</h2>
            <p>{t("workoutPlan.generationMethodBody")}</p>
          </div>
          <div className="workout-generation-method__choices">
            <label><input type="radio" name="workout-generation-method" checked={generationMethod === "fitsho_coach"} disabled={savingGenerationMethod} onChange={() => changeGenerationMethod("fitsho_coach")} />{t("workoutPlan.fitshoCoach")}</label>
            <label><input type="radio" name="workout-generation-method" checked={generationMethod === "ai"} disabled={savingGenerationMethod} onChange={() => changeGenerationMethod("ai")} />{t("workoutPlan.aiCoach")}</label>
          </div>
        </section>

        {state === "loading" && <StatusPanel role="status" message={t("workoutPlan.loading")} />}
        {state === "error" && plan === null && (
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
                message={t(
                  generationError === "cooldown"
                    ? "workoutPlan.generateCooldown"
                    : "workoutPlan.generateError",
                )}
                action={generationError === "failed" ? t("common.retry") : undefined}
                onAction={generationError === "failed" ? generate : undefined}
              />
            )}
            <section className="workout-empty" aria-labelledby="workout-empty-title">
              <h2 id="workout-empty-title" className="fitsho-display">{t("workoutPlan.emptyTitle")}</h2>
              <p>{t("workoutPlan.emptyBody")}</p>
              <GenerateButton
                generating={generating}
                onClick={generate}
                disabled={generationError === "cooldown"}
              />
            </section>
          </>
        )}
        {state === "ready" && plan !== null && (
          <>
            <CoachReviewBanner plan={plan} isEnglish={isEnglish} historical={isViewingHistorical} />
            {history.length > 1 && (
              <section className="workout-version-history" aria-labelledby="workout-version-history-title">
                <div>
                  <p className="eyebrow eyebrow--accent">{l("نسخه‌های برنامه", "Plan versions")}</p>
                  <h2 id="workout-version-history-title">{l("تاریخچه برنامه", "Plan history")}</h2>
                </div>
                <div className="workout-version-history__list">
                  {history.map((version) => {
                    const approved = version.coach_review.state === "coach_approved";
                    const label = approved
                      ? l("نسخه تأیید مربی", "Coach-approved version")
                      : l("نسخه اولیه", "Initial version");
                    return (
                      <button
                        type="button"
                        key={version.id}
                        className={version.id === plan.id ? "workout-version-history__active" : undefined}
                        disabled={selectingVersionId !== null}
                        aria-label={`${label} — ${new Intl.DateTimeFormat(isEnglish ? "en" : "fa-IR", { dateStyle: "medium" }).format(new Date(version.created_at))}`}
                        onClick={() => selectVersion(version)}
                      >
                        <strong>{label}</strong>
                        <span>{version.is_active ? l("فعال", "Active") : l("آرشیو", "Archived")}</span>
                      </button>
                    );
                  })}
                </div>
              </section>
            )}
            {reused && <p className="workout-reused" role="status">{t("workoutPlan.reused")}</p>}
            {plan.is_stale && (
              <p className="workout-stale" role="status">{t("workoutPlan.stale")}</p>
            )}
            {plan.body_analysis_provenance?.provisional === true && (
              <p className="workout-body-analysis-warning" role="alert">
                {t("workoutPlan.provisionalBodyAnalysisWarning")}
              </p>
            )}
            {generationError && (
              <StatusPanel
                role="alert"
                message={t(
                  generationError === "cooldown"
                    ? "workoutPlan.generateCooldown"
                    : "workoutPlan.generateError",
                )}
                action={generationError === "failed" ? t("common.retry") : undefined}
                onAction={generationError === "failed" ? generate : undefined}
              />
            )}
            {plan.ai_coach_program_explanation_fa && (
              <aside className="workout-ai-coach" aria-label={t("workoutPlan.aiCoach")}>
                <span className="workout-ai-coach__icon" aria-hidden="true">✦</span>
                <div><p>{t("workoutPlan.aiCoach")}</p><strong>{plan.ai_coach_program_explanation_fa}</strong></div>
              </aside>
            )}
            <section className="workout-schedule" aria-labelledby="workout-schedule-title">
              <div className="workout-schedule__heading">
                <div>
                  <p className="eyebrow eyebrow--accent">{t("workoutPlan.weekly")}</p>
                  <h2 id="workout-schedule-title" className="fitsho-display">{t("workoutPlan.scheduleTitle")}</h2>
                </div>
                {!isViewingHistorical && (
                  <GenerateButton
                    generating={generating}
                    onClick={generate}
                    update
                    disabled={generationError === "cooldown"}
                  />
                )}
              </div>
              {generating && <p className="workout-generating" role="status">{t("workoutPlan.generating")}</p>}
              <div className="workout-days">
                {plan.days.map((day) => (
                  <article className="workout-day" key={day.day_number}>
                    <header>
                      <span>{String(day.day_number).padStart(2, "0")}</span>
                      <div>
                        <h3>{isEnglish ? day.title_en : day.title_fa}</h3>
                        <p>{t("workoutPlan.sessionMinutes", { count: day.estimated_duration_minutes })}</p>
                      </div>
                    </header>
                    {day.ai_coach_explanation_fa && (
                      <aside className="workout-ai-coach workout-ai-coach--day">
                        <span className="workout-ai-coach__icon" aria-hidden="true">✦</span>
                        <div><p>{t("workoutPlan.aiCoach")}</p><strong>{day.ai_coach_explanation_fa}</strong></div>
                      </aside>
                    )}
                    <ol>
                      {day.exercises.map((item) => (
                        <li className="workout-exercise" key={item.order_index}>
                          <ExerciseMedia
                            path={item.exercise.media_path}
                            name={isEnglish ? item.exercise.name_en : item.exercise.name_fa}
                            mediaType={item.exercise.media_type}
                          />
                          <div className="workout-exercise__content">
                            <h4>{isEnglish ? item.exercise.name_en : item.exercise.name_fa}</h4>
                            <dl>
                              <div><dt>{t("workoutPlan.sets")}</dt><dd>{item.sets}</dd></div>
                              <div><dt>{t("workoutPlan.reps")}</dt><dd>{item.reps_min}–{item.reps_max}</dd></div>
                              <div><dt>{t("workoutPlan.rest")}</dt><dd>{item.rest_seconds}{t("workoutPlan.seconds")}</dd></div>
                              <div><dt>{t("workoutPlan.rir")}</dt><dd>{item.rir}</dd></div>
                            </dl>
                            {(isEnglish ? item.notes_en : item.notes_fa) !== null && (
                              <p>{isEnglish ? item.notes_en : item.notes_fa}</p>
                            )}
                            <Link to={`/exercises/${item.exercise.slug}`}>{t("workoutPlan.detail")}</Link>
                            {item.alternatives.length > 0 && (
                              <details className="workout-alternatives">
                                <summary>{t("workoutPlan.alternatives")}</summary>
                                <ul>
                                  {item.alternatives.map((alternative) => (
                                    <li key={alternative.exercise.id}>
                                      <Link to={`/exercises/${alternative.exercise.slug}`}>
                                        {isEnglish
                                          ? alternative.exercise.name_en
                                          : alternative.exercise.name_fa}
                                      </Link>
                                      <span>{isEnglish ? alternative.reason_en : alternative.reason_fa}</span>
                                    </li>
                                  ))}
                                </ul>
                              </details>
                            )}
                          </div>
                        </li>
                      ))}
                    </ol>
                  </article>
                ))}
              </div>
            </section>
          </>
        )}

        <section className="workout-future" aria-labelledby="workout-future-title">
          <h2 id="workout-future-title">{t("workoutPlan.futureTitle")}</h2>
          <div>
            {[
              ["pdf", "workoutPlan.pdf"],
              ["feedback", "workoutPlan.feedback"],
            ].map(([key, translationKey]) => (
              <article key={key}>
                <h3>{t(`${translationKey}.title`)}</h3>
                <p>{t(`${translationKey}.body`)}</p>
                <button type="button" disabled aria-label={t(`${translationKey}.title`)}>{t("workoutPlan.comingSoon")}</button>
              </article>
            ))}
            <article>
              <h3>{t("workoutPlan.body.title")}</h3>
              <p>{t("workoutPlan.body.body")}</p>
              <Link className="workout-future__link" to="/body-progress">
                {t("workoutPlan.body.action")}
              </Link>
            </article>
          </div>
        </section>
      </main>
    </div>
  );
}

function CoachReviewBanner({ plan, isEnglish, historical }: { plan: WorkoutPlan; isEnglish: boolean; historical: boolean }) {
  const review = plan.coach_review;
  const l = (fa: string, en: string) => isEnglish ? en : fa;
  if (historical) {
    return <p className="workout-review-banner workout-review-banner--history" role="status">{l("در حال مشاهده نسخه قبلی", "Viewing a previous version")}</p>;
  }
  if (review?.state === "pending_coach_review") {
    return (
      <aside className="workout-review-banner workout-review-banner--pending" role="status">
        <strong>{l("در انتظار تأیید مربی", "Waiting for coach approval")}</strong>
        <span>{l("نسخه اولیه فعال است و بعد از تأیید، نسخه جدید جایگزین آن می‌شود.", "The initial version stays active until the approved version is ready.")}</span>
      </aside>
    );
  }
  if (review?.state === "coach_approved") {
    const coach = review.coach_display_name ?? l("مربی فیتشو", "Fitsho coach");
    return (
      <aside className="workout-review-banner workout-review-banner--approved" role="status">
        <strong>{l(`تأییدشده توسط ${coach}`, `Approved by ${coach}`)}</strong>
        {review.approved_at && <time dateTime={review.approved_at}>{new Intl.DateTimeFormat(isEnglish ? "en" : "fa-IR", { dateStyle: "long" }).format(new Date(review.approved_at))}</time>}
        {review.coach_note && <p>{review.coach_note}</p>}
      </aside>
    );
  }
  return null;
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
