import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

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
      <div className={`plan-paper plan-paper--${type}`} aria-hidden="true">
        <div className="plan-paper__head"><i /><span /></div>
        <div className="plan-paper__lines"><i /><i /><i /><i /><i /></div>
        <VerificationSeal type={type} />
      </div>
    </section>
  );
}

function VerificationSeal({ type }: { type: "training" | "nutrition" }) {
  const { t } = useTranslation();

  return (
    <div className="verification-seal" data-testid="verification-seal">
      <svg viewBox="0 0 120 120" aria-hidden="true">
        <circle className="verification-seal__track" cx="60" cy="60" r="52" />
        <circle className="verification-seal__ring" cx="60" cy="60" r="52" pathLength="100" />
        <path className="verification-seal__check" pathLength="100" d="M35 60 52 77 87 40" />
      </svg>
      <small>{t(`landing.supervision.${type}.seal`)}</small>
    </div>
  );
}
