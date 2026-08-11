import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import foodPhoto from "../../assets/landing/food.webp";
import landingFilm from "../../assets/landing/landfilm.mp4";
import landingPoster from "../../assets/landing/landfilm-poster.webp";
import { useScrollProgress } from "./useScrollProgress";

export function CinematicStory({ reducedMotion }: { reducedMotion: boolean }) {
  const { t } = useTranslation();
  const storyRef = useScrollProgress<HTMLElement>("cinematic", reducedMotion);

  return (
    <section className="cinematic-story" ref={storyRef} aria-label={t("landing.story.label")}>
      <div className="cinematic-story__stage">
        <video
          className="cinematic-story__film"
          data-testid="landing-film"
          src={landingFilm}
          poster={landingPoster}
          autoPlay={!reducedMotion}
          muted
          playsInline
          loop
          preload="metadata"
          aria-hidden="true"
        />
        <div className="cinematic-story__shade" aria-hidden="true" />

        <section className="cinematic-hero" aria-labelledby="landing-hero-title">
          <div className="cinematic-hero__copy">
            <h1 id="landing-hero-title" className="fitsho-display">{t("landing.hero.title")}</h1>
            <p>{t("landing.hero.body")}</p>
            <Link className="landing-primary-cta" to="/get-started">
              {t("landing.cta")}<span aria-hidden="true">←</span>
            </Link>
          </div>
          <span className="cinematic-hero__scroll" aria-hidden="true"><i /></span>
        </section>

        <SupervisionMoment type="training" />
        <SupervisionMoment type="nutrition" />
        <MealPhotoAnalysis />
      </div>
    </section>
  );
}

function MealPhotoAnalysis() {
  const { t } = useTranslation();

  return (
    <section
      className="meal-analysis"
      aria-labelledby="landing-meal-title"
    >
      <div className="meal-analysis__copy">
        <p>MEAL PHOTO ANALYSIS</p>
        <h2 id="landing-meal-title" className="fitsho-display">{t("landing.meal.title")}</h2>
        <small>{t("landing.meal.estimate")}</small>
      </div>
      <div className="meal-analysis__visual">
        <div className="scan-frame scan-frame--meal">
          <img
            data-testid="meal-photo"
            src={foodPhoto}
            alt={t("landing.meal.imageAlt")}
            width="560"
            height="540"
            loading="lazy"
          />
          <span className="scan-frame__corner scan-frame__corner--one" aria-hidden="true" />
          <span className="scan-frame__corner scan-frame__corner--two" aria-hidden="true" />
          <span className="scan-frame__corner scan-frame__corner--three" aria-hidden="true" />
          <span className="scan-frame__corner scan-frame__corner--four" aria-hidden="true" />
          <i className="scan-frame__line" data-testid="meal-scan-line" aria-hidden="true" />
        </div>
        <div className="meal-result" aria-label={t("landing.meal.resultLabel")}>
          <strong>{t("landing.meal.calories")}</strong>
          <div>
            {(["protein", "carbs", "fat"] as const).map((macro) => (
              <span key={macro}>
                <small>{t(`landing.meal.macros.${macro}.label`)}</small>
                <b>{t(`landing.meal.macros.${macro}.value`)}</b>
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function SupervisionMoment({ type }: { type: "training" | "nutrition" }) {
  const { t } = useTranslation();
  const titleId = `landing-${type}-title`;

  return (
    <section
      className={`supervision-moment supervision-moment--${type}`}
      aria-labelledby={titleId}
    >
      <div className="supervision-moment__copy">
        <p>{type.toUpperCase()}</p>
        <h2 id={titleId} className="fitsho-display">{t(`landing.supervision.${type}.title`)}</h2>
      </div>
      <div
        className={`plan-paper plan-paper--${type}`}
        data-testid="plan-document"
        aria-hidden="true"
      >
        <div className="plan-paper__head"><i /><span /></div>
        <div className="plan-paper__content">
          <div className="plan-paper__group"><i /><i /><i /></div>
          <div className="plan-paper__group"><i /><i /></div>
          <div className="plan-paper__group"><i /><i /><i /></div>
        </div>
        <VerificationSeal type={type} />
      </div>
    </section>
  );
}

function VerificationSeal({ type }: { type: "training" | "nutrition" }) {
  const { t } = useTranslation();

  return (
    <div className="verification-seal" data-testid="verification-seal">
      <div className="verification-seal__medallion">
        <svg viewBox="0 0 120 120" aria-hidden="true">
          <circle className="verification-seal__track" cx="60" cy="60" r="52" />
          <circle className="verification-seal__ring" cx="60" cy="60" r="52" pathLength="100" />
          <path className="verification-seal__check" pathLength="100" d="M35 60 52 77 87 40" />
        </svg>
      </div>
      <small>{t(`landing.supervision.${type}.seal`)}</small>
    </div>
  );
}
