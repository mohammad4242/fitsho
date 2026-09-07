import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { BodyAnalysisExperienceIndicators } from "./types";

interface BodyAnalysisScoreStripProps {
  indicators: BodyAnalysisExperienceIndicators;
}

interface ScoreItem {
  id: string;
  titleKey: string;
  score: number | null;
  statusBadge?: string;
  statusText?: string;
  tone: "balance" | "symmetry" | "upper_lower";
}

export function BodyAnalysisScoreStrip({ indicators }: BodyAnalysisScoreStripProps) {
  const { t } = useTranslation();

  // 1. Muscle Balance
  const muscleBalanceScore = indicators.muscle_balance !== undefined
    ? indicators.muscle_balance.score_percent
    : (indicators.body_shape?.score_percent ?? null);
  const muscleBalanceStatus = muscleBalanceScore !== null && muscleBalanceScore >= 80
    ? t("bodyAnalysis.indicators.states.balanced", { defaultValue: "متعادل" })
    : "";

  // 2. Visual Symmetry
  const symmetryScore = indicators.visible_symmetry?.score_percent;
  const symmetryStatusKey = indicators.visible_symmetry?.status;
  const symmetryStatus = symmetryStatusKey
    ? t(`bodyAnalysis.indicators.states.${symmetryStatusKey}`, { defaultValue: "" })
    : (symmetryScore !== null && symmetryScore >= 85 ? t("bodyAnalysis.indicators.states.strong_symmetry", { defaultValue: "تقارن بالا" }) : "");

  // 3. Upper / Lower Body Balance
  const upperLowerScore = indicators.upper_lower_balance?.score_percent;
  const upperLowerStatusKey = indicators.upper_lower_balance?.status;
  const upperLowerStatus = upperLowerStatusKey
    ? t(`bodyAnalysis.indicators.states.${upperLowerStatusKey}`, { defaultValue: "" })
    : (upperLowerScore !== null && upperLowerScore < 80 ? t("bodyAnalysis.indicators.states.needs_improvement", { defaultValue: "نیازمند بهبود" }) : "");

  const items: ScoreItem[] = [
    {
      id: "muscle_balance",
      titleKey: "bodyAnalysis.indicators.muscleBalance.title",
      score: muscleBalanceScore,
      statusBadge: muscleBalanceStatus,
      statusText: t("bodyAnalysis.indicators.muscleBalance.message", { defaultValue: "توسعه متوازن عضلات" }),
      tone: "balance",
    },
    {
      id: "visible_symmetry",
      titleKey: "bodyAnalysis.indicators.visibleSymmetry.title",
      score: symmetryScore,
      statusBadge: symmetryStatus || t("bodyAnalysis.indicators.visibleSymmetry.title"),
      statusText: t("bodyAnalysis.indicators.visibleSymmetry.alignedSubtitle", { defaultValue: "هماهنگی و تقارن مطلوب" }),
      tone: "symmetry",
    },
    {
      id: "upper_lower_balance",
      titleKey: "bodyAnalysis.indicators.upperLowerBalance.title",
      score: upperLowerScore,
      statusBadge: upperLowerStatus || t("bodyAnalysis.indicators.upperLowerBalance.title"),
      statusText: t("bodyAnalysis.indicators.upperLowerBalance.laggingSubtitle", { defaultValue: "توازن بالا و پایین‌تنه" }),
      tone: "upper_lower",
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
            statusBadge={item.statusBadge}
            subtitle={item.statusText}
            tone={item.tone}
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
  statusBadge,
  subtitle,
  tone,
}: {
  id: string;
  title: string;
  score: number | null;
  statusBadge?: string;
  subtitle?: string;
  tone: "balance" | "symmetry" | "upper_lower";
}) {
  const [showInfo, setShowInfo] = useState(false);
  const radius = 34;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = score !== null
    ? circumference - (circumference * Math.min(100, Math.max(0, score))) / 100
    : circumference;

  return (
    <article
      className={`fitsho-score-ring-card fitsho-score-ring-card--${tone}`}
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
          viewBox="0 0 88 88"
          width="76"
          height="76"
          aria-hidden="true"
        >
          {/* Background track */}
          <circle
            className="fitsho-score-ring-card__track"
            cx="44"
            cy="44"
            r={radius}
            strokeWidth="5.5"
            fill="none"
          />
          {/* Progress fill */}
          {score !== null && (
            <circle
              className={`fitsho-score-ring-card__fill fitsho-score-ring-card__fill--${tone}`}
              cx="44"
              cy="44"
              r={radius}
              strokeWidth="5.5"
              fill="none"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              transform="rotate(-90 44 44)"
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
        <div className="fitsho-score-ring-card__title-row">
          <h3 className="fitsho-score-ring-card__title">{title}</h3>
          <button
            type="button"
            className="fitsho-score-ring-card__info-btn"
            onClick={() => setShowInfo(!showInfo)}
            aria-label={`${title} info`}
          >
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 16v-4M12 8h.01" />
            </svg>
          </button>
        </div>

        {statusBadge && (
          <span className={`fitsho-score-ring-card__status-badge fitsho-score-ring-card__status-badge--${tone}`}>
            {statusBadge}
          </span>
        )}

        {subtitle && (
          <p className="fitsho-score-ring-card__subtitle">{subtitle}</p>
        )}

        {showInfo && subtitle && (
          <p className="fitsho-score-ring-card__info-popover">{subtitle}</p>
        )}
      </div>
    </article>
  );
}
