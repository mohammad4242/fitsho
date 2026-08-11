import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";
import { getLatestWeeklyNutritionPlan } from "../features/nutrition/api";
import { useProfile } from "../features/profile/ProfileContext";
import { generateWorkoutPlan, getActiveWorkoutPlan } from "../features/workouts/api";
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
  const [generating, setGenerating] = useState(false);
  const [nutritionState, setNutritionState] = useState<NutritionState>("loading");

  useEffect(() => {
    if (!hasTraining) {
      setPlanState("empty");
      return;
    }
    let active = true;
    void getActiveWorkoutPlan()
      .then((plan) => { if (active) setPlanState(plan === null ? "empty" : "ready"); })
      .catch(() => { if (active) setPlanState("error"); });
    return () => { active = false; };
  }, [hasTraining]);

  useEffect(() => {
    if (!hasNutrition) {
      setNutritionState("empty");
      return;
    }
    let active = true;
    void getLatestWeeklyNutritionPlan()
      .then((plan) => {
        if (active) setNutritionState(plan === null ? "empty" : plan.physician_approved ? "ready" : "pending");
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

  return (
    <main className="command-center fitsho-page">
      <div className="command-center__container">
        <header className="command-center__welcome">
          <p className="fitsho-section-heading__eyebrow">{t("dashboard.kicker")}</p>
          <h1 className="fitsho-display">{t("dashboard.greeting", { name: profile?.display_name ?? (english ? "there" : "دوست") })}</h1>
          <p>{t("dashboard.commandIntro")}</p>
        </header>

        {profile === null && (
          <Link className="fitsho-button" to="/onboarding">{t("dashboard.completeProfile")}</Link>
        )}

        <section className="command-center__grid" aria-label={t("dashboard.statusLabel")}>
          {hasTraining && (
            <article className="command-card command-card--primary">
              <div className="command-card__head">
                <div>
                  <p>{t("dashboard.trainingEyebrow")}</p>
                  <h2>{t("dashboard.todayWorkout")}</h2>
                </div>
                <span className={`fitsho-status fitsho-status--${planState === "ready" ? "success" : "neutral"}`}>
                  {t(`dashboard.planState.${planState}`)}
                </span>
              </div>
              {planDuration !== undefined && (
                <p className="command-card__context">
                  {t("dashboard.planDuration", { count: planDuration.toLocaleString(english ? "en-US" : "fa-IR") })}
                </p>
              )}
              <p className="command-card__body">{t("dashboard.trainingBody")}</p>
              <PrimaryAction state={planState} generating={generating} onStart={startWorkout} />
            </article>
          )}

          {hasNutrition && (
            <Link
              className="command-card command-card--nutrition"
              to="/nutrition-estimate"
              aria-label={t("dashboard.nutritionAria")}
            >
              <div className="command-card__head">
                <div><p>{t("dashboard.nutritionEyebrow")}</p><h2>{t("dashboard.nutritionTitle")}</h2></div>
                <span className="fitsho-status fitsho-status--neutral">{t(`dashboard.nutritionState.${nutritionState}`)}</span>
              </div>
              <p className="command-card__body">{t("dashboard.nutritionBody")}</p>
              <span className="command-card__link">{t("dashboard.viewTargets")} <b aria-hidden="true">←</b></span>
            </Link>
          )}

          <Link
            className="command-card command-card--progress"
            to="/body-progress"
            aria-label={t("workoutPlan.body.action")}
          >
            <div className="command-card__head">
              <div><p>{t("dashboard.progressEyebrow")}</p><h2>{t("dashboard.progressTitle")}</h2></div>
            </div>
            <p className="command-card__body">{t("dashboard.progressBody")}</p>
            <span className="command-card__link">{t("workoutPlan.body.action")} <b aria-hidden="true">←</b></span>
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
