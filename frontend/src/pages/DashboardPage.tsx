import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";
import { getDailyTracking, getLatestWeeklyNutritionPlan } from "../features/nutrition/api";
import type { DailyTrackingSummary, WeeklyPlan } from "../features/nutrition/types";
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
    void Promise.all([getLatestWeeklyNutritionPlan(), getDailyTracking(today).catch(() => null)])
      .then(([latestPlan, tracking]) => {
        if (active) {
          setNutritionPlan(latestPlan);
          setDailyTracking(tracking);
          setNutritionState(latestPlan === null ? "empty" : latestPlan.physician_approved ? "ready" : "pending");
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
  const actual = dailyTracking?.actual_totals;
  const format = (value: number) => Math.round(value).toLocaleString(locale);

  return (
    <main className="command-center fitsho-page">
      <div className="command-center__container">
        <header className="command-center__welcome">
          <h1 className="fitsho-display">{t("dashboard.greeting", { name: profile?.display_name ?? (english ? "there" : "دوست") })}</h1>
          <p>{english ? "Ready for today?" : "برای امروز آماده‌ای؟"}</p>
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
                <div className="command-card__workout">
                  <span>{String(nextDay.day_number).padStart(2, "0")}</span>
                  <div><h3>{english ? nextDay.title_en : nextDay.title_fa}</h3><p>{format(nextDay.estimated_duration_minutes)} {english ? "min" : "دقیقه"}</p></div>
                </div>
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
              <div className="command-card__head"><div><p>{t("dashboard.nutritionEyebrow")}</p><h2>{t("dashboard.nutritionTitle")}</h2></div></div>
              {planned ? <>
                <div className="command-card__calories">
                  <div><strong>{format(actual?.energy_kcal ?? planned.energy_kcal ?? 0)}</strong><span>{actual ? `${english ? "of" : "از"} ${format(planned.energy_kcal ?? 0)} kcal` : english ? "daily target" : "هدف روزانه"}</span></div>
                  {actual && <ProgressRing value={actual.energy_kcal ?? 0} max={planned.energy_kcal ?? 0} />}
                </div>
                <div className="fitsho-metric-strip">
                  <span><strong>{format(actual?.protein_g ?? planned.protein_g ?? 0)}g</strong><small>{english ? "Protein" : "پروتئین"}</small></span>
                  <span><strong>{format(actual?.carbohydrate_g ?? planned.carbohydrate_g ?? 0)}g</strong><small>{english ? "Carbs" : "کربوهیدرات"}</small></span>
                  <span><strong>{format(actual?.total_fat_g ?? planned.total_fat_g ?? 0)}g</strong><small>{english ? "Fat" : "چربی"}</small></span>
                </div>
              </> : <span className="command-card__empty">{t(`dashboard.nutritionState.${nutritionState}`)}</span>}
            </Link>
          )}

          <Link
            className="command-card command-card--progress"
            to="/body-progress"
            aria-label={t("workoutPlan.body.action")}
          >
            <div className="command-card__head"><div><p>{t("dashboard.progressEyebrow")}</p><h2>{t("dashboard.progressTitle")}</h2></div><span className="command-card__arrow" aria-hidden="true">←</span></div>
            {profile?.current_weight_kg !== undefined && <div className="command-card__progress-metric"><strong>{profile.current_weight_kg.toLocaleString(locale)}</strong><span>kg · {english ? "current weight" : "وزن فعلی"}</span></div>}
          </Link>
        </section>

        <nav className="command-center__quick" aria-label={t("dashboard.quickActions") }>
          {hasTraining && <Link to="/workout-plan">{t("header.workoutPlan")}</Link>}
          {hasTraining && <Link to="/exercises">{t("header.exercises")}</Link>}
          {hasNutrition && <Link to="/food-catalogue">{t("header.foodCatalogue")}</Link>}
          <Link to="/profile">{t("header.profile")}</Link>
        </nav>
      </div>
    </main>
  );
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
