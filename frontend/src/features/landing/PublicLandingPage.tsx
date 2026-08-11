import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { LanguageSwitcher } from "../../shared/LanguageSwitcher";
import { BodyIntelligence } from "./BodyIntelligence";
import { CinematicStory } from "./CinematicStory";
import { ProcessStory } from "./ProcessStory";
import "./publicLanding.css";
import "./landingStory.css";

function useReducedMotion() {
  const [reducedMotion, setReducedMotion] = useState(
    () => typeof window.matchMedia === "function"
      && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(query.matches);
    query.addEventListener?.("change", update);
    return () => query.removeEventListener?.("change", update);
  }, []);

  return reducedMotion;
}

export function PublicLandingPage() {
  const { i18n, t } = useTranslation();
  const language = i18n.resolvedLanguage === "en" ? "en" : "fa";
  const reducedMotion = useReducedMotion();
  const [menuOpen, setMenuOpen] = useState(false);

  const previews = ["dashboard", "workout", "nutrition", "body", "catalogue"] as const;

  return (
    <main
      className="public-landing fitsho-page"
      data-language={language}
      data-reduced-motion={String(reducedMotion)}
      dir={language === "fa" ? "rtl" : "ltr"}
    >
      <header className="landing-header">
        <Link className="brand-mark" to="/" aria-label={t("common.brand")}>
          <span className="brand-mark__pulse" aria-hidden="true" />
          {t("common.brand")}
        </Link>
        <nav className="landing-header__nav" aria-label={t("landing.menu.label")}>
          <a href="#how-it-works">{t("landing.menu.how")}</a>
          <a href="#product">{t("landing.menu.product")}</a>
          <Link to="/login">{t("landing.menu.signIn")}</Link>
        </nav>
        <div className="landing-header__actions">
          <LanguageSwitcher />
          <button
            className="landing-menu-button"
            type="button"
            aria-label={t(menuOpen ? "landing.menu.close" : "landing.menu.open")}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <span /><span />
          </button>
        </div>
      </header>

      {menuOpen && (
        <aside className="landing-menu" role="dialog" aria-label={t("landing.menu.label")}>
          <button
            type="button"
            aria-label={t("landing.menu.close")}
            onClick={() => setMenuOpen(false)}
          >×</button>
          <nav>
            <a href="#how-it-works" onClick={() => setMenuOpen(false)}>{t("landing.menu.how")}</a>
            <a href="#product" onClick={() => setMenuOpen(false)}>{t("landing.menu.product")}</a>
            <Link to="/get-started">{t("landing.menu.build")}</Link>
            <Link to="/login">{t("landing.menu.signIn")}</Link>
          </nav>
        </aside>
      )}

      <CinematicStory reducedMotion={reducedMotion} />
      <ProcessStory reducedMotion={reducedMotion} />
      <BodyIntelligence reducedMotion={reducedMotion} />

      <section className="landing-product" id="product" aria-labelledby="landing-product-title">
        <div className="landing-section-heading">
          <p className="landing-kicker">{t("landing.product.eyebrow")}</p>
          <h2 id="landing-product-title" className="fitsho-display">{t("landing.product.title")}</h2>
          <p>{t("landing.product.body")}</p>
        </div>
        <div className="landing-product-grid">
          {previews.map((preview, index) => (
            <article className={`landing-product-card landing-product-card--${preview}`} key={preview}>
              <header><span>{String(index + 1).padStart(2, "0")}</span><h3>{t(`landing.product.previews.${preview}`)}</h3></header>
              <ProductPreview type={preview} />
            </article>
          ))}
        </div>
      </section>

      <section className="landing-final" aria-labelledby="landing-final-title">
        <p className="landing-kicker">{t("landing.final.eyebrow")}</p>
        <h2 id="landing-final-title" className="fitsho-display">{t("landing.final.title")}</h2>
        <p>{t("landing.final.body")}</p>
        <Link className="landing-primary-cta" to="/get-started">
          {t("landing.cta")}<span aria-hidden="true">←</span>
        </Link>
      </section>

      <footer className="landing-footer">
        <Link className="brand-mark" to="/"><span className="brand-mark__pulse" aria-hidden="true" />{t("common.brand")}</Link>
        <span>© 2026 Fitsho</span>
      </footer>
    </main>
  );
}

function ProductPreview({ type }: { type: "dashboard" | "workout" | "nutrition" | "body" | "catalogue" }) {
  const { t } = useTranslation();

  if (type === "workout") {
    return (
      <div className="landing-preview landing-preview--workout">
        {(["pushDay", "pullDay", "legDay"] as const).map((day, index) => (
          <span key={day} data-active={index === 0 ? "true" : undefined}>
            <b>{t(`landing.product.sample.${day}`)}</b><small>{t("landing.product.sample.session")}</small>
          </span>
        ))}
      </div>
    );
  }
  if (type === "nutrition") {
    return (
      <div className="landing-preview landing-preview--nutrition">
        <strong>2,340 <small>kcal</small></strong>
        <span>{t("landing.product.sample.protein")}</span>
        <span>{t("landing.product.sample.carbs")}</span>
        <span>{t("landing.product.sample.fat")}</span>
      </div>
    );
  }
  if (type === "body") {
    return (
      <div className="landing-preview landing-preview--body">
        <i /><span /><b />
        <ul>
          <li>{t("landing.product.sample.shouldersPriority")}</li>
          <li>{t("landing.product.sample.backBalanced")}</li>
          <li>{t("landing.product.sample.confidence")}</li>
        </ul>
      </div>
    );
  }
  if (type === "catalogue") {
    return (
      <div className="landing-preview landing-preview--catalogue">
        <span><b>{t("landing.product.sample.milk")}</b><small>61 kcal</small></span>
        <span><b>{t("landing.product.sample.chicken")}</b><small>165 kcal</small></span>
      </div>
    );
  }
  return (
    <div className="landing-preview landing-preview--dashboard">
      <span><small>{t("landing.product.sample.todayWorkout")}</small><strong>{t("landing.product.sample.pushDay")}</strong></span>
      <span><small>{t("landing.callouts.nutrition")}</small><strong>{t("landing.callouts.calories")}</strong></span>
      <span><small>{t("landing.intelligence.confidence")}</small><strong>{t("landing.intelligence.confidenceValue")}</strong></span>
    </div>
  );
}
