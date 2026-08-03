import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import planFocusFallback from "../../assets/landing/plan-focus-fallback.jpg";
import planFocusVideo from "../../assets/landing/plan-focus.mp4";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { ApiError } from "../../shared/apiClient";
import { getProfile, updateProfile } from "../profile/api";
import type { WorkoutGenerationMethod } from "../profile/types";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import { ExerciseMedia } from "../exercises/ExerciseMedia";
import { generateWorkoutPlan, getActiveWorkoutPlan } from "./api";
import type { WorkoutPlan } from "./types";
import "./workoutPlan.css";

type PlanState = "loading" | "empty" | "ready" | "error";

export function WorkoutPlanPage({ planDurationWeeks }: { planDurationWeeks: number }) {
  const { i18n, t } = useTranslation();
  const [plan, setPlan] = useState<WorkoutPlan | null>(null);
  const [state, setState] = useState<PlanState>("loading");
  const [generating, setGenerating] = useState(false);
  const [reused, setReused] = useState(false);
  const [generationError, setGenerationError] = useState<"cooldown" | "failed" | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [generationMethod, setGenerationMethod] = useState<WorkoutGenerationMethod>("fitsho_coach");
  const [savingGenerationMethod, setSavingGenerationMethod] = useState(false);
  const isEnglish = i18n.resolvedLanguage === "en";
  const displayedPlanDuration = plan?.plan_duration_weeks ?? planDurationWeeks;

  useEffect(() => {
    let active = true;
    setState("loading");
    void getActiveWorkoutPlan()
      .then((currentPlan) => {
        if (!active) return;
        setPlan(currentPlan);
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
        setState("ready");
        setReused(result.reused);
      })
      .catch((error: unknown) => {
        const errorKind = error instanceof ApiError && error.status === 429 ? "cooldown" : "failed";
        setState(plan === null ? "empty" : "ready");
        setGenerationError(errorKind);
      })
      .finally(() => setGenerating(false));
  }

  return (
    <div className="workout-plan-shell">
      <MemberHeaderMedia
        imageSrc={planFocusFallback}
        videoSrc={planFocusVideo}
        className="member-page-background"
      />
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
                <GenerateButton
                  generating={generating}
                  onClick={generate}
                  update
                  disabled={generationError === "cooldown"}
                />
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
