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
          <a href="#body-analysis">{t("landing.menu.analysis")}</a>
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
            <a href="#body-analysis" onClick={() => setMenuOpen(false)}>{t("landing.menu.analysis")}</a>
            <Link to="/get-started">{t("landing.menu.build")}</Link>
            <Link to="/login">{t("landing.menu.signIn")}</Link>
          </nav>
        </aside>
      )}

      <CinematicStory reducedMotion={reducedMotion} />
      <ProcessStory reducedMotion={reducedMotion} />
      <BodyIntelligence reducedMotion={reducedMotion} />

      <section className="landing-final" aria-labelledby="landing-final-title">
        <h2 id="landing-final-title" className="fitsho-display">{t("landing.final.title")}</h2>
        <Link className="landing-primary-cta" to="/get-started">
          {t("landing.final.action")}<span aria-hidden="true">←</span>
        </Link>
      </section>
    </main>
  );
}
