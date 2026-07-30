import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import heroStrengthFallback from "../assets/landing/hero-strength-fallback.jpg";
import heroStrengthVideo from "../assets/landing/hero-strength.mp4";
import { useAuth } from "../features/auth/AuthContext";
import { useProfile } from "../features/profile/ProfileContext";
import { generateWorkoutPlan, getActiveWorkoutPlan } from "../features/workouts/api";
import { AuthenticatedHeader } from "../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../shared/MemberHeaderMedia";
import "./dashboard.css";

type PlanState = "loading" | "empty" | "ready" | "error";

export function DashboardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { profile } = useProfile();
  const [planState, setPlanState] = useState<PlanState>("loading");
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    let active = true;
    void getActiveWorkoutPlan()
      .then((plan) => {
        if (active) setPlanState(plan === null ? "empty" : "ready");
      })
      .catch(() => {
        if (active) setPlanState("error");
      });
    return () => {
      active = false;
    };
  }, []);

  if (user === null || profile === null) {
    return null;
  }

  function startWorkout() {
    setGenerating(true);
    void generateWorkoutPlan()
      .then(() => navigate("/workout-plan"))
      .finally(() => setGenerating(false));
  }

  return (
    <main className="today-shell">
      <MemberHeaderMedia
        imageSrc={heroStrengthFallback}
        videoSrc={heroStrengthVideo}
        className="member-page-background"
      />
      <AuthenticatedHeader />

      <section className="today-hero" aria-labelledby="today-title">
        <div className="today-hero__content">
          <p className="today-kicker">{t("dashboard.kicker")}</p>
          <h1 id="today-title" className="fitsho-display">
            {t("dashboard.greeting", { name: profile.display_name })}
          </h1>
          <p>{t("dashboard.intro")}</p>
          <PrimaryAction state={planState} generating={generating} onStart={startWorkout} />
        </div>
        <p className="today-hero__hint" aria-hidden="true">{t("dashboard.scrollHint")}</p>
      </section>

      <section className="today-actions" aria-label={t("dashboard.quickActions")}>
        <Link to="/workout-plan" className="today-actions__card">
          <span>01</span>
          <div>
            <p>{t("dashboard.planCardEyebrow")}</p>
            <h2>{t("dashboard.planCardTitle")}</h2>
          </div>
          <b aria-hidden="true">↖</b>
        </Link>
        <Link to="/exercises" className="today-actions__card today-actions__card--aqua">
          <span>02</span>
          <div>
            <p>{t("dashboard.catalogEyebrow")}</p>
            <h2>{t("dashboard.catalogTitle")}</h2>
          </div>
          <b aria-hidden="true">↖</b>
        </Link>
      </section>
    </main>
  );
}

function PrimaryAction({ state, generating, onStart }: { state: PlanState; generating: boolean; onStart: () => void }) {
  const { t } = useTranslation();

  if (state === "ready") {
    return <Link className="today-primary-action" to="/workout-plan">{t("dashboard.start")}</Link>;
  }

  return (
    <button className="today-primary-action" type="button" onClick={onStart} disabled={state === "loading" || generating}>
      {generating ? t("dashboard.generating") : t("dashboard.start")}
    </button>
  );
}
