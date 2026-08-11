import type { CSSProperties } from "react";
import { useTranslation } from "react-i18next";

import { useScrollProgress } from "./useScrollProgress";

const stages = ["understand", "plan", "train", "adapt"] as const;

export function ProcessStory({ reducedMotion }: { reducedMotion: boolean }) {
  const { t } = useTranslation();
  const processRef = useScrollProgress<HTMLElement>("process", reducedMotion);

  return (
    <section
      className="process-story"
      id="how-it-works"
      ref={processRef}
      aria-labelledby="landing-process-title"
    >
      <div className="process-story__stage">
        <header>
          <p className="landing-kicker">{t("landing.process.eyebrow")}</p>
          <h2 id="landing-process-title" className="fitsho-display">{t("landing.process.title")}</h2>
        </header>
        <ol className="process-steps" aria-label={t("landing.progression.label")}>
          {stages.map((stage, index) => (
            <li key={stage} data-stage={stage} style={{ "--stage-index": index } as CSSProperties}>
              <div className="process-step__marker" aria-hidden="true">
                <svg viewBox="0 0 84 84">
                  <circle className="process-step__track" cx="42" cy="42" r="36" />
                  <circle className="process-step__ring" cx="42" cy="42" r="36" pathLength="100" />
                </svg>
                <span>{String(index + 1).padStart(2, "0")}</span>
              </div>
              <div className="process-step__copy">
                <strong>{t(`landing.progression.${stage}.title`)}</strong>
                <small>{t(`landing.progression.${stage}.body`)}</small>
              </div>
              {index < stages.length - 1 && <span className="process-step__connector" aria-hidden="true"><i /></span>}
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
