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

      <div
        className="body-interface"
        data-testid="body-interface"
        data-active-muscle={activeMuscle}
      >
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

        <svg className="body-interface__muscles" viewBox="0 0 100 150" aria-hidden="true">
          <defs>
            <radialGradient id="body-muscle-aqua" cx="50%" cy="42%" r="68%">
              <stop offset="0" stopColor="#9ff8ed" stopOpacity=".55" />
              <stop offset=".48" stopColor="#50dfce" stopOpacity=".26" />
              <stop offset="1" stopColor="#50dfce" stopOpacity="0" />
            </radialGradient>
            <filter id="body-muscle-soft" x="-45%" y="-45%" width="190%" height="190%">
              <feGaussianBlur stdDeviation="1.8" />
            </filter>
          </defs>
          <g
            className="muscle-region muscle-region--shoulders"
            data-region="shoulders"
            data-active={activeMuscle === "shoulders"}
          >
            <path className="muscle-region__glow" filter="url(#body-muscle-soft)" d="M22 35 C22 27 29 23 38 25 C43 26 47 30 49 35 C42 34 36 36 30 43 C25 43 22 40 22 35 Z M51 35 C53 30 57 26 62 25 C71 23 78 27 78 35 C78 40 75 43 70 43 C64 36 58 34 51 35 Z" />
            <path className="muscle-region__light" d="M24 34 C25 28 31 26 38 27 C42 28 45 31 47 34 C40 34 34 37 30 41 C27 41 24 38 24 34 Z M53 34 C55 31 58 28 62 27 C69 26 75 28 76 34 C76 38 73 41 70 41 C66 37 60 34 53 34 Z" />
          </g>
          <g
            className="muscle-region muscle-region--back"
            data-region="back"
            data-active={activeMuscle === "back"}
          >
            <path className="muscle-region__glow" filter="url(#body-muscle-soft)" d="M33 36 C39 32 45 33 50 39 C55 33 61 32 67 36 L69 58 C64 68 58 74 50 77 C42 74 36 68 31 58 Z" />
            <path className="muscle-region__light" d="M36 37 C41 34 46 36 50 41 C54 36 59 34 64 37 L66 56 C62 64 57 69 50 72 C43 69 38 64 34 56 Z" />
          </g>
        </svg>

        <svg className="body-interface__connectors" viewBox="0 0 100 150" aria-hidden="true">
          <path className="connector connector--shoulders" d="M72 34 C80 34 82 30 90 30" pathLength="100" />
          <path className="connector connector--back" d="M58 57 C73 57 78 74 90 74" pathLength="100" />
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
