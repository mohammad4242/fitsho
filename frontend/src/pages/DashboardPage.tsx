import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import heroStrengthFallback from "../assets/landing/hero-strength-fallback.jpg";
import heroStrengthVideo from "../assets/landing/hero-strength.mp4";
import planFocusFallback from "../assets/landing/plan-focus-fallback.jpg";
import planFocusVideo from "../assets/landing/plan-focus.mp4";
import progressDriveFallback from "../assets/landing/progress-drive-fallback.jpg";
import progressDriveVideo from "../assets/landing/progress-drive.mp4";
import { useAuth } from "../features/auth/AuthContext";
import { useProfile } from "../features/profile/ProfileContext";
import { generateWorkoutPlan, getActiveWorkoutPlan } from "../features/workouts/api";
import { AuthenticatedHeader } from "../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../shared/MemberHeaderMedia";
import "./dashboard.css";

type PlanState = "loading" | "empty" | "ready" | "error";

export function DashboardPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { profile } = useProfile();
  const [planState, setPlanState] = useState<PlanState>("loading");
  const [generating, setGenerating] = useState(false);
  const [storyStage, setStoryStage] = useState<"plan" | "progress">("plan");
  const planChapter = useRef<HTMLElement>(null);
  const progressChapter = useRef<HTMLElement>(null);

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
          setStoryStage(entry.target === progressChapter.current ? "progress" : "plan");
        });
      },
      { threshold: 0.55 },
    );
    if (planChapter.current) observer.observe(planChapter.current);
    if (progressChapter.current) observer.observe(progressChapter.current);
    return () => observer.disconnect();
  }, []);

  if (user === null) {
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
            {t("dashboard.greeting", { name: profile?.display_name ?? (i18n.language === "en" ? "there" : "دوست" ) })}
          </h1>
          <p>{t("dashboard.intro")}</p>
          {profile === null ? <Link className="primary-button" to="/onboarding">{i18n.language === "en" ? "Complete profile" : "تکمیل پروفایل"}</Link> : <PrimaryAction state={planState} generating={generating} onStart={startWorkout} />}
        </div>
        <p className="today-hero__hint" aria-hidden="true">{t("dashboard.scrollHint")}</p>
      </section>

      <section className="today-story" aria-label={t("dashboard.storyLabel")} data-stage={storyStage}>
        <div className="today-story__sticky" aria-hidden="true">
          <MemberHeaderMedia
            imageSrc={planFocusFallback}
            videoSrc={planFocusVideo}
            active={storyStage === "plan"}
            className="today-story__video today-story__video--plan"
          />
          <MemberHeaderMedia
            imageSrc={progressDriveFallback}
            videoSrc={progressDriveVideo}
            active={storyStage === "progress"}
            className="today-story__video today-story__video--progress"
          />
        </div>
        <div className="today-story__chapters">
          <article className="today-story__chapter" ref={planChapter}>
            <span>01</span>
            <div>
              <p className="today-kicker">{t("dashboard.storyOneEyebrow")}</p>
              <h2 className="fitsho-display">{t("dashboard.storyOneTitle")}</h2>
              <p>{t("dashboard.storyOneBody")}</p>
            </div>
          </article>
          <article className="today-story__chapter today-story__chapter--progress" ref={progressChapter}>
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
