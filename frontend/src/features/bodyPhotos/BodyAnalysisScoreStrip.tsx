import { useTranslation } from "react-i18next";
import type { BodyAnalysisExperienceIndicators } from "./types";

interface BodyAnalysisScoreStripProps {
  indicators: BodyAnalysisExperienceIndicators;
}

interface ScoreItem {
  id: string;
  titleKey: string;
  score: number | null;
  statusText?: string;
}

export function BodyAnalysisScoreStrip({ indicators }: BodyAnalysisScoreStripProps) {
  const { t } = useTranslation();

  // 1. Muscle Balance
  const muscleBalanceScore = indicators.muscle_balance !== undefined
    ? indicators.muscle_balance.score_percent
    : (indicators.body_shape?.score_percent ?? null);
  // 2. Visual Symmetry
  const symmetryScore = indicators.visible_symmetry?.score_percent;
  const symmetryStatusKey = indicators.visible_symmetry?.status;
  const symmetryStatus = symmetryStatusKey
    ? t(`bodyAnalysis.indicators.states.${symmetryStatusKey}`, { defaultValue: "" })
    : "";

  // 3. Upper / Lower Body Balance
  const upperLowerScore = indicators.upper_lower_balance?.score_percent;
  const upperLowerStatusKey = indicators.upper_lower_balance?.status;
  const upperLowerStatus = upperLowerStatusKey
    ? t(`bodyAnalysis.indicators.states.${upperLowerStatusKey}`, { defaultValue: "" })
    : "";

  const items: ScoreItem[] = [
    {
      id: "muscle_balance",
      titleKey: "bodyAnalysis.indicators.muscleBalance.title",
      score: muscleBalanceScore,
      statusText: t("bodyAnalysis.indicators.muscleBalance.message", { defaultValue: "توسعه متوازن عضلات" }),
    },
    {
      id: "visible_symmetry",
      titleKey: "bodyAnalysis.indicators.visibleSymmetry.title",
      score: symmetryScore,
      statusText: symmetryStatus || t("bodyAnalysis.indicators.visibleSymmetry.title"),
    },
    {
      id: "upper_lower_balance",
      titleKey: "bodyAnalysis.indicators.upperLowerBalance.title",
      score: upperLowerScore,
      statusText: upperLowerStatus || t("bodyAnalysis.indicators.upperLowerBalance.title"),
    },
  ];

  return (
    <section className="fitsho-score-strip" aria-labelledby="fitsho-score-strip-title">
      <header className="fitsho-score-strip__header">
        <h2 id="fitsho-score-strip-title">{t("bodyAnalysis.indicators.title")}</h2>
      </header>
      <div className="fitsho-score-strip__grid" role="list">
        {items.map((item) => (
          <ScoreRingCard
            key={item.id}
            id={item.id}
            title={t(item.titleKey)}
            score={item.score}
            subtitle={item.statusText}
          />
        ))}
      </div>
    </section>
  );
}

function ScoreRingCard({
  id,
  title,
  score,
  subtitle,
}: {
  id: string;
  title: string;
  score: number | null;
  subtitle?: string;
}) {
  const radius = 38;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = score !== null
    ? circumference - (circumference * Math.min(100, Math.max(0, score))) / 100
    : circumference;

  return (
    <article
      className="fitsho-score-ring-card"
      data-testid="body-analysis-score-row"
      data-score-id={id}
      role="listitem"
    >
      <div
        className="fitsho-score-ring-card__ring-wrap"
        role="progressbar"
        aria-label={title}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={score ?? undefined}
      >
        <svg
          className="fitsho-score-ring-card__svg"
          viewBox="0 0 96 96"
          width="96"
          height="96"
          aria-hidden="true"
        >
          {/* Background track */}
          <circle
            className="fitsho-score-ring-card__track"
            cx="48"
            cy="48"
            r={radius}
            strokeWidth="6"
            fill="none"
          />
          {/* Progress fill */}
          {score !== null && (
            <circle
              className="fitsho-score-ring-card__fill"
              cx="48"
              cy="48"
              r={radius}
              strokeWidth="6"
              fill="none"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              transform="rotate(-90 48 48)"
            />
          )}
        </svg>
        <div className="fitsho-score-ring-card__center">
          <span className="fitsho-score-ring-card__score">
            {score !== null ? `${score}%` : "—"}
          </span>
        </div>
      </div>

      <div className="fitsho-score-ring-card__meta">
        <h3 className="fitsho-score-ring-card__title">{title}</h3>
        {subtitle && (
          <p className="fitsho-score-ring-card__subtitle">{subtitle}</p>
        )}
      </div>
    </article>
  );
}
