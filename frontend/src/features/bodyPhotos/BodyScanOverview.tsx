import { useState } from "react";
import { useTranslation } from "react-i18next";

import femaleHeroArtwork from "../../assets/body1/female-hero.png";
import maleHeroArtwork from "../../assets/body1/male-hero.png";
import type { BodyAnalysisExperienceV4 } from "./types";

type OverviewView = "front" | "side" | "back";

interface BodyScanOverviewProps {
  experience: BodyAnalysisExperienceV4;
  summaryMessage: string;
  routeMessage: string;
}

export function BodyScanOverview({
  experience,
  summaryMessage,
  routeMessage,
}: BodyScanOverviewProps) {
  const { t } = useTranslation();
  const [activeView, setActiveView] = useState<OverviewView>("front");
  const [showBfInfo, setShowBfInfo] = useState(false);
  const [showBmiInfo, setShowBmiInfo] = useState(false);

  const sex = experience.input_snapshot.sex;
  const heroImage = sex === "female" ? femaleHeroArtwork : maleHeroArtwork;

  const bodyComp = experience.body_composition;
  const bodyFat = bodyComp?.estimated_body_fat_percent;
  const bmi = bodyComp?.bmi;

  const views: Array<{ id: OverviewView; label: string; icon: string }> = [
    { id: "front", label: t("bodyAnalysis.topOverview.front"), icon: "M12 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6zm-4 8a2 2 0 0 0-2 2v5a2 2 0 0 0 2 2h1v5a1 1 0 0 0 2 0v-5h2v5a1 1 0 0 0 2 0v-5h1a2 2 0 0 0 2-2v-5a2 2 0 0 0-2-2H8z" },
    { id: "side", label: t("bodyAnalysis.topOverview.side"), icon: "M13 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6zm-3 8a2 2 0 0 0-2 2v5a2 2 0 0 0 2 2h1v5a1 1 0 0 0 2 0v-5h1a2 2 0 0 0 2-2v-5a2 2 0 0 0-2-2h-2z" },
    { id: "back", label: t("bodyAnalysis.topOverview.back"), icon: "M12 2a3 3 0 1 0 0 6 3 3 0 0 0 0-6zm-4 8a2 2 0 0 0-2 2v5a2 2 0 0 0 2 2h1v5a1 1 0 0 0 2 0v-5h2v5a1 1 0 0 0 2 0v-5h1a2 2 0 0 0 2-2v-5a2 2 0 0 0-2-2H8z" },
  ];

  // Helper for BMI category
  function getBmiCategory(val: number | null | undefined): string {
    if (val === null || val === undefined) return "";
    if (val < 18.5) return t("bodyAnalysis.topOverview.bmiUnderweight", { defaultValue: "زیر وزن نرمال" });
    if (val < 25) return t("bodyAnalysis.topOverview.bmiNormal", { defaultValue: "محدوده نرمال" });
    if (val < 30) return t("bodyAnalysis.topOverview.bmiOverweight", { defaultValue: "اضافه وزن" });
    return t("bodyAnalysis.topOverview.bmiObese", { defaultValue: "چاقی" });
  }

  // Calculate percentage along a 10%-35% scale for body fat bar
  const bfBarPercent = bodyFat != null ? Math.min(100, Math.max(0, ((bodyFat - 10) / 25) * 100)) : 0;
  // Calculate percentage along 15-35 scale for BMI bar
  const bmiBarPercent = bmi != null ? Math.min(100, Math.max(0, ((bmi - 15) / 20) * 100)) : 0;

  return (
    <section className="fitsho-scan-overview" aria-label={t("bodyAnalysis.topOverview.title")}>
      <div className="fitsho-scan-overview__stage">
        {/* LEFT: View Selector */}
        <nav className="fitsho-scan-overview__views" aria-label={t("bodyAnalysis.topOverview.title")}>
          {views.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`fitsho-scan-overview__view-btn ${activeView === item.id ? "fitsho-scan-overview__view-btn--active" : ""}`}
              onClick={() => setActiveView(item.id)}
              aria-pressed={activeView === item.id}
            >
              <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18" aria-hidden="true">
                <path d={item.icon} />
              </svg>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        {/* CENTER: Hero Body Asset */}
        <div className="fitsho-scan-overview__hero" data-view={activeView}>
          <div className="fitsho-scan-overview__hero-glow" aria-hidden="true" />
          <img
            src={heroImage}
            alt={t("bodyAnalysis.topOverview.heroAlt")}
            className="fitsho-scan-overview__hero-img"
          />
          <div className="fitsho-scan-overview__view-tag">
            <span>{t(`bodyAnalysis.topOverview.${activeView}`)}</span>
          </div>
        </div>

        {/* RIGHT: Metric Cards & Summary */}
        <div className="fitsho-scan-overview__sidebar">
          {/* Card 1: Estimated Body Fat % */}
          <div className="fitsho-scan-card fitsho-scan-card--metric" data-testid="body-fat-card">
            <header className="fitsho-scan-card__header">
              <div className="fitsho-scan-card__title-row">
                <span className="fitsho-scan-card__eyebrow">{t("bodyAnalysis.topOverview.bodyFatTitle")}</span>
                <button
                  type="button"
                  className="fitsho-scan-card__info-trigger"
                  onClick={() => setShowBfInfo(!showBfInfo)}
                  aria-label="اطلاعات درصد چربی"
                >
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 16v-4M12 8h.01" />
                  </svg>
                </button>
              </div>
              <span className="fitsho-scan-card__badge">{t("bodyAnalysis.topOverview.bodyFatMethod")}</span>
            </header>

            <div className="fitsho-scan-card__value-row">
              <span className="fitsho-scan-card__value">
                {bodyFat != null ? `${bodyFat}%` : "—"}
              </span>
            </div>

            {showBfInfo && (
              <p className="fitsho-scan-card__info-text" role="note">
                {t("bodyAnalysis.topOverview.infoTooltipBodyFat")}
              </p>
            )}

            <div className="fitsho-scan-card__track-container">
              <div
                className="fitsho-scan-card__track"
                role="progressbar"
                aria-valuenow={bodyFat ?? undefined}
                aria-valuemin={5}
                aria-valuemax={40}
                aria-label={t("bodyAnalysis.topOverview.bodyFatTitle")}
              >
                <div
                  className="fitsho-scan-card__bar"
                  style={{ width: `${bfBarPercent}%` }}
                />
              </div>
              <span className="fitsho-scan-card__track-hint">
                {t("bodyAnalysis.topOverview.estimateNotice")}
              </span>
            </div>
          </div>

          {/* Card 2: BMI */}
          <div className="fitsho-scan-card fitsho-scan-card--metric" data-testid="bmi-card">
            <header className="fitsho-scan-card__header">
              <div className="fitsho-scan-card__title-row">
                <span className="fitsho-scan-card__eyebrow">{t("bodyAnalysis.topOverview.bmiTitle")}</span>
                <button
                  type="button"
                  className="fitsho-scan-card__info-trigger"
                  onClick={() => setShowBmiInfo(!showBmiInfo)}
                  aria-label="اطلاعات BMI"
                >
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M12 16v-4M12 8h.01" />
                  </svg>
                </button>
              </div>
              {bmi != null && (
                <span className="fitsho-scan-card__badge fitsho-scan-card__badge--neutral">
                  {getBmiCategory(bmi)}
                </span>
              )}
            </header>

            <div className="fitsho-scan-card__value-row">
              <span className="fitsho-scan-card__value">
                {bmi != null ? bmi : "—"}
              </span>
            </div>

            {showBmiInfo && (
              <p className="fitsho-scan-card__info-text" role="note">
                {t("bodyAnalysis.topOverview.infoTooltipBmi")}
              </p>
            )}

            <div className="fitsho-scan-card__track-container">
              <div
                className="fitsho-scan-card__track"
                role="progressbar"
                aria-valuenow={bmi ?? undefined}
                aria-valuemin={15}
                aria-valuemax={35}
                aria-label={t("bodyAnalysis.topOverview.bmiTitle")}
              >
                <div
                  className="fitsho-scan-card__bar fitsho-scan-card__bar--bmi"
                  style={{ width: `${bmiBarPercent}%` }}
                />
              </div>
              <span className="fitsho-scan-card__track-hint">
                {t("bodyAnalysis.topOverview.bmiCategory")}
              </span>
            </div>
          </div>

          {/* Card 3: Fitsho Summary */}
          <div className="fitsho-scan-card fitsho-scan-card--summary" data-testid="first-look-summary">
            <header className="fitsho-scan-card__summary-header">
              <span className="fitsho-scan-card__summary-icon" aria-hidden="true">✦</span>
              <h2 className="fitsho-scan-card__summary-title">
                {t("bodyAnalysis.firstImpression.title")}
              </h2>
            </header>
            <p className="fitsho-scan-card__summary-text">{summaryMessage}</p>
            {routeMessage && (
              <p className="fitsho-scan-card__summary-route">{routeMessage}</p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
