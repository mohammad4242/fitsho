import { useState } from "react";
import { useTranslation } from "react-i18next";

import bodyFallback from "../../assets/landing/body.png";
import bodyImage from "../../assets/landing/body.webp";
import { useScrollProgress } from "./useScrollProgress";

const muscles = ["shoulders", "back"] as const;
type Muscle = (typeof muscles)[number];

export function BodyIntelligence({ reducedMotion }: { reducedMotion: boolean }) {
  const { t } = useTranslation();
  const [activeMuscle, setActiveMuscle] = useState<Muscle>("shoulders");
  const bodyRef = useScrollProgress<HTMLElement>("body", reducedMotion);

  return (
    <section
      className="body-intelligence"
      ref={bodyRef}
      aria-labelledby="landing-intelligence-title"
    >
      <header className="body-intelligence__heading">
        <p className="landing-kicker">{t("landing.intelligence.eyebrow")}</p>
        <h2 id="landing-intelligence-title" className="fitsho-display">{t("landing.intelligence.title")}</h2>
        <p>{t("landing.intelligence.body")}</p>
      </header>

      <div className="body-interface" data-active-muscle={activeMuscle}>
        <picture className="body-interface__image">
          <source srcSet={bodyImage} type="image/webp" />
          <img
            data-testid="fitsho-body-intelligence"
            src={bodyFallback}
            alt={t("landing.intelligence.imageAlt")}
            width="1024"
            height="1536"
            loading="lazy"
          />
        </picture>

        <svg className="body-interface__muscles" viewBox="0 0 100 150" preserveAspectRatio="none" aria-hidden="true">
          <path className="muscle-shape muscle-shape--shoulders" d="M25 38 C31 29 39 29 48 35 C40 38 34 44 29 50 C24 48 21 44 25 38 Z M52 35 C61 29 69 29 75 38 C79 44 76 48 71 50 C66 44 60 38 52 35 Z" />
          <path className="muscle-shape muscle-shape--back" d="M36 38 C43 34 47 37 50 41 C53 37 57 34 64 38 L67 62 C61 71 56 74 50 75 C44 74 39 71 33 62 Z" />
        </svg>

        <svg className="body-interface__connectors" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <path className="connector connector--shoulders" d="M68 30 C79 30 81 22 92 22" pathLength="100" />
          <path className="connector connector--back" d="M52 43 C70 43 77 61 92 61" pathLength="100" />
        </svg>

        <div className="body-interface__hotspots">
          {muscles.map((muscle) => (
            <button
              key={muscle}
              className={`body-hotspot body-hotspot--${muscle}`}
              type="button"
              aria-label={t(`landing.callouts.${muscle}`)}
              aria-pressed={activeMuscle === muscle}
              onClick={() => setActiveMuscle(muscle)}
              onFocus={() => setActiveMuscle(muscle)}
              onPointerEnter={(event) => {
                if (event.pointerType !== "touch") setActiveMuscle(muscle);
              }}
            ><span /></button>
          ))}
        </div>

        <div className="body-interface__callout" role="status" aria-live="polite">
          <small>{t(`landing.callouts.${activeMuscle}`)}</small>
          <strong>{t(`landing.intelligence.muscles.${activeMuscle}`)}</strong>
        </div>
      </div>
    </section>
  );
}
