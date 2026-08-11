import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import bodyAnalysisImage from "../assets/landing/body.webp";
import foodAnalysisImage from "../assets/landing/food.webp";
import { useAuth } from "../features/auth/AuthContext";
import { ExerciseMedia } from "../features/exercises/ExerciseMedia";
import { getCurrentNutritionEstimate, getDailyTracking, getLatestWeeklyNutritionPlan } from "../features/nutrition/api";
import type { DailyTrackingSummary, NutritionEstimate, WeeklyPlan } from "../features/nutrition/types";
import { useProfile } from "../features/profile/ProfileContext";
import { generateWorkoutPlan, getActiveWorkoutPlan } from "../features/workouts/api";
import type { WorkoutPlan } from "../features/workouts/types";
import { ProgressRing } from "../shared/ProgressRing";
import "./dashboard.css";

type PlanState = "loading" | "empty" | "ready" | "error";
type NutritionState = "loading" | "pending" | "ready" | "empty";

export function DashboardPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { profile, productMode } = useProfile();
  const hasTraining = productMode === undefined || productMode === "training" || productMode === "both";
  const hasNutrition = productMode === "nutrition" || productMode === "both";
  const [planState, setPlanState] = useState<PlanState>("loading");
  const [plan, setPlan] = useState<WorkoutPlan | null>(null);
  const [generating, setGenerating] = useState(false);
  const [nutritionState, setNutritionState] = useState<NutritionState>("loading");
  const [nutritionPlan, setNutritionPlan] = useState<WeeklyPlan | null>(null);
  const [nutritionEstimate, setNutritionEstimate] = useState<NutritionEstimate | null>(null);
  const [dailyTracking, setDailyTracking] = useState<DailyTrackingSummary | null>(null);

  useEffect(() => {
    if (!hasTraining) {
      setPlanState("empty");
      return;
    }
    let active = true;
    void getActiveWorkoutPlan()
      .then((activePlan) => {
        if (!active) return;
        setPlan(activePlan);
        setPlanState(activePlan === null ? "empty" : "ready");
      })
      .catch(() => { if (active) setPlanState("error"); });
    return () => { active = false; };
  }, [hasTraining]);

  useEffect(() => {
    if (!hasNutrition) {
      setNutritionState("empty");
      return;
    }
    let active = true;
    const today = new Date().toISOString().slice(0, 10);
    void Promise.all([
      getLatestWeeklyNutritionPlan(),
      getCurrentNutritionEstimate(),
      getDailyTracking(today).catch(() => null),
    ])
      .then(([latestPlan, estimate, tracking]) => {
        if (active) {
          setNutritionPlan(latestPlan);
          setNutritionEstimate(estimate);
          setDailyTracking(tracking);
          setNutritionState(latestPlan !== null
            ? latestPlan.physician_approved ? "ready" : "pending"
            : estimate !== null ? "ready" : "empty");
        }
      })
      .catch(() => { if (active) setNutritionState("empty"); });
    return () => { active = false; };
  }, [hasNutrition]);

  if (user === null) return null;

  function startWorkout() {
    setGenerating(true);
    void generateWorkoutPlan()
      .then(() => navigate("/workout-plan"))
      .finally(() => setGenerating(false));
  }

  const english = i18n.resolvedLanguage === "en";
  const planDuration = profile?.plan_duration_weeks;
  const locale = english ? "en-US" : "fa-IR";
  const nextDay = plan?.days?.[0];
  const currentDate = new Date().toISOString().slice(0, 10);
  const todayPlan = nutritionPlan?.days?.find((day) => day.plan_date === currentDate) ?? nutritionPlan?.days?.[0];
  const planned = todayPlan?.nutrient_totals;
  const estimated = nutritionEstimate?.targets;
  const nutritionTarget = {
    energy_kcal: planned?.energy_kcal ?? estimated?.goal_calories?.preferred ?? null,
    protein_g: planned?.protein_g ?? estimated?.protein?.preferred ?? null,
    carbohydrate_g: planned?.carbohydrate_g ?? estimated?.carbohydrate?.preferred ?? null,
    total_fat_g: planned?.total_fat_g ?? estimated?.total_fat?.preferred ?? null,
  };
  const trackedTotals = dailyTracking?.actual_totals;
  const hasActual = trackedTotals !== undefined && (
    dailyTracking?.data_status === "sufficient"
    || (dailyTracking?.entries?.length ?? 0) > 0
    || Object.values(trackedTotals).some((value) => value > 0)
  );
  const actual = hasActual ? trackedTotals : null;
  const hasNutritionTarget = nutritionTarget.energy_kcal !== null;
  const format = (value: number) => Math.round(value).toLocaleString(locale);
  const displayName = profile?.display_name ?? (english ? "there" : "دوست");
  const avatarInitial = displayName.trim().charAt(0).toLocaleUpperCase(locale);

  return (
    <main className="command-center fitsho-page">
      <div className="command-center__container">
        <header className="command-center__welcome">
          <Link className="command-center__avatar" to="/profile" aria-label={t("header.profile")}>
            {avatarInitial}
          </Link>
          <div>
            <h1 className="fitsho-display">{t("dashboard.greeting", { name: displayName })}</h1>
            <p>{english ? "Ready for today?" : "برای امروز آماده‌ای؟"}</p>
          </div>
          <span className="command-center__live" aria-hidden="true" />
        </header>

        {profile === null && (
          <Link className="fitsho-button" to="/onboarding">{t("dashboard.completeProfile")}</Link>
        )}

        <section className="command-center__grid" aria-label={t("dashboard.statusLabel")}>
          {hasTraining && (
            <article className="command-card command-card--primary" role="region" aria-labelledby="dashboard-today-workout">
              <div className="command-card__head">
                <div>
                  <p>{t("dashboard.trainingEyebrow")}</p>
                  <h2 id="dashboard-today-workout">{t("dashboard.todayWorkout")}</h2>
                </div>
                <span className={`fitsho-status fitsho-status--${planState === "ready" ? "success" : "neutral"}`}>
                  {t(`dashboard.planState.${planState}`)}
                </span>
              </div>
              {nextDay ? (
                <>
                  <div className="command-card__workout">
                    <span>{String(nextDay.day_number).padStart(2, "0")}</span>
                    <div><h3>{english ? nextDay.title_en : nextDay.title_fa}</h3><p>{format(nextDay.estimated_duration_minutes)} {english ? "min" : "دقیقه"}</p></div>
                  </div>
                  {nextDay.exercises[0]?.exercise.media_path && <div className="command-card__media"><ExerciseMedia ambient path={nextDay.exercises[0].exercise.media_path} name={english ? nextDay.exercises[0].exercise.name_en : nextDay.exercises[0].exercise.name_fa} mediaType={nextDay.exercises[0].exercise.media_type} /></div>}
                </>
              ) : planDuration !== undefined ? <p className="command-card__context">{t("dashboard.planDuration", { count: planDuration.toLocaleString(locale) })}</p> : null}
              <PrimaryAction state={planState} generating={generating} onStart={startWorkout} />
            </article>
          )}

          {hasNutrition && (
            <Link
              className="command-card command-card--nutrition"
              to="/nutrition-estimate"
              aria-label={t("dashboard.nutritionAria")}
            >
              <div className="command-card__head"><div><p>{t("dashboard.nutritionEyebrow")}</p><h2>{t("dashboard.nutritionTitle")}</h2></div><span className="command-card__arrow" aria-hidden="true">←</span></div>
              {hasNutritionTarget ? <>
                <div className="command-card__calories">
                  <div><strong>{format(actual?.energy_kcal ?? nutritionTarget.energy_kcal ?? 0)}</strong><span>{actual ? `${english ? "of" : "از"} ${format(nutritionTarget.energy_kcal ?? 0)} kcal` : english ? "daily target" : "هدف روزانه"}</span></div>
                  <ProgressRing value={actual?.energy_kcal ?? 0} max={nutritionTarget.energy_kcal ?? 0} label={english ? "Today's calorie progress" : "پیشرفت کالری امروز"} />
                </div>
                <div className="fitsho-metric-strip">
                  <span><strong>{formatMetric(actual?.protein_g ?? nutritionTarget.protein_g, format)}</strong><small>{english ? "Protein" : "پروتئین"}</small></span>
                  <span><strong>{formatMetric(actual?.carbohydrate_g ?? nutritionTarget.carbohydrate_g, format)}</strong><small>{english ? "Carbs" : "کربوهیدرات"}</small></span>
                  <span><strong>{formatMetric(actual?.total_fat_g ?? nutritionTarget.total_fat_g, format)}</strong><small>{english ? "Fat" : "چربی"}</small></span>
                </div>
              </> : <span className="command-card__empty">{t(`dashboard.nutritionState.${nutritionState}`)}</span>}
            </Link>
          )}

        </section>

        <nav className="command-center__quick" aria-label={t("dashboard.quickActions") }>
          <DashboardQuickAction
            image={bodyAnalysisImage}
            title="body analys"
            to="/body-progress"
          />
          {hasNutrition && (
            <DashboardQuickAction
              image={foodAnalysisImage}
              title="food analys"
              to="/nutrition-tracking"
            />
          )}
        </nav>
      </div>
    </main>
  );
}

function DashboardQuickAction({ image, title, to }: { image: string; title: string; to: string }) {
  return (
    <Link className="command-quick-card" to={to} aria-label={title}>
      <img src={image} alt="" />
      <i className="command-quick-card__scan" aria-hidden="true" />
      <span dir="ltr">{title}</span>
    </Link>
  );
}

function formatMetric(value: number | null | undefined, format: (value: number) => string) {
  return value === null || value === undefined ? "—" : `${format(value)}g`;
}

function PrimaryAction({ state, generating, onStart }: { state: PlanState; generating: boolean; onStart: () => void }) {
  const { t } = useTranslation();
  if (state === "ready") {
    return <Link className="fitsho-button command-card__action" to="/workout-plan">{t("dashboard.start")}</Link>;
  }
  return (
    <button className="fitsho-button command-card__action" type="button" onClick={onStart} disabled={state === "loading" || generating}>
      {generating ? t("dashboard.generating") : t("dashboard.start")}
    </button>
  );
}
