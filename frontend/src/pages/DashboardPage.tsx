import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import heroStrengthFallback from "../assets/landing/hero-strength-fallback.jpg";
import heroStrengthVideo from "../assets/landing/hero-strength.mp4";
import planFocusFallback from "../assets/landing/plan-focus-fallback.jpg";
import progressDriveFallback from "../assets/landing/progress-drive-fallback.jpg";
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
  const [storyStage, setStoryStage] = useState<"gym" | "lift">("gym");
  const gymChapter = useRef<HTMLElement>(null);
  const liftChapter = useRef<HTMLElement>(null);

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

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          setStoryStage(entry.target === liftChapter.current ? "lift" : "gym");
        });
      },
      { threshold: 0.55 },
    );
    if (gymChapter.current) observer.observe(gymChapter.current);
    if (liftChapter.current) observer.observe(liftChapter.current);
    return () => observer.disconnect();
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

      <section className="today-story" aria-label={t("dashboard.storyLabel")} data-stage={storyStage}>
        <div className="today-story__sticky" aria-hidden="true">
          <img src={planFocusFallback} alt="" className="today-story__image today-story__image--gym" />
          <img src={progressDriveFallback} alt="" className="today-story__image today-story__image--lift" />
          <div className="today-story__shade" />
        </div>
        <div className="today-story__chapters">
          <article className="today-story__chapter" ref={gymChapter}>
            <span>01</span>
            <div>
              <p className="today-kicker">{t("dashboard.storyOneEyebrow")}</p>
              <h2 className="fitsho-display">{t("dashboard.storyOneTitle")}</h2>
              <p>{t("dashboard.storyOneBody")}</p>
            </div>
          </article>
          <article className="today-story__chapter today-story__chapter--lift" ref={liftChapter}>
            <span>02</span>
            <div>
              <p className="today-kicker">{t("dashboard.storyTwoEyebrow")}</p>
              <h2 className="fitsho-display">{t("dashboard.storyTwoTitle")}</h2>
              <p>{t("dashboard.storyTwoBody")}</p>
            </div>
          </article>
        </div>
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
