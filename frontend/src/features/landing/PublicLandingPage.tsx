import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import bodyHeroFallback from "../../assets/landing/fitsho-body-hero-3d.jpg";
import bodyHero from "../../assets/landing/fitsho-body-hero-3d.webp";
import { LanguageSwitcher } from "../../shared/LanguageSwitcher";
import "./publicLanding.css";

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

  const inputs = ["goal", "experience", "days", "duration", "considerations"] as const;
  const progression = ["understand", "plan", "train", "adapt"] as const;
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

      <section className="landing-hero" aria-labelledby="landing-hero-title">
        <div className="landing-hero__copy">
          <p className="landing-kicker">{t("landing.hero.eyebrow")}</p>
          <h1 id="landing-hero-title" className="fitsho-display">{t("landing.hero.title")}</h1>
          <p>{t("landing.hero.body")}</p>
          <Link className="landing-primary-cta" to="/get-started">
            {t("landing.cta")}<span aria-hidden="true">←</span>
          </Link>
        </div>

        <div className="landing-hero__visual" aria-label={t("landing.hero.visualLabel")}>
          <picture>
            <source srcSet={bodyHero} type="image/webp" />
            <img
              data-testid="fitsho-body-hero"
              src={bodyHeroFallback}
              alt=""
              aria-hidden="true"
              width="1672"
              height="941"
              fetchPriority="high"
            />
          </picture>
          <div className="landing-callout landing-callout--shoulders">
            <span>{t("landing.callouts.shoulders")}</span>
            <strong>{t("landing.callouts.priority")}</strong>
          </div>
          <div className="landing-callout landing-callout--back">
            <span>{t("landing.callouts.back")}</span>
            <strong>{t("landing.callouts.balanced")}</strong>
          </div>
          <div className="landing-callout landing-callout--confidence">
            <span>{t("landing.intelligence.confidence")}</span>
            <strong>{t("landing.intelligence.confidenceValue")}</strong>
          </div>
        </div>
        <PlanBuilder compact />
        <p className="landing-hero__note">{t("landing.hero.note")}</p>
      </section>

      <section className="landing-system" id="how-it-works" aria-labelledby="landing-system-title">
        <div className="landing-section-heading">
          <p className="landing-kicker">{t("landing.system.eyebrow")}</p>
          <h2 id="landing-system-title" className="fitsho-display">{t("landing.system.title")}</h2>
          <p>{t("landing.system.body")}</p>
        </div>

        <ol className="landing-progression" aria-label={t("landing.progression.label")}>
          {progression.map((step, index) => (
            <li key={step}>
              <span>{new Intl.NumberFormat(language === "fa" ? "fa-IR" : "en").format(index + 1)}</span>
              <strong>{t(`landing.progression.${step}.title`)}</strong>
              <small>{t(`landing.progression.${step}.body`)}</small>
            </li>
          ))}
        </ol>

        <div className="landing-transformation">
          <div className="landing-inputs" aria-label={t("landing.inputs.label")}>
            <header>{t("landing.inputs.label")}</header>
            {inputs.map((input) => (
              <article key={input}>
                <span>{t(`landing.inputs.${input}.label`)}</span>
                <strong>{t(`landing.inputs.${input}.value`)}</strong>
              </article>
            ))}
          </div>
          <span className="landing-transformation__flow" aria-hidden="true">←</span>
          <PlanBuilder />
        </div>
      </section>

      <section className="landing-intelligence" aria-labelledby="landing-intelligence-title">
        <div className="landing-body-interface" aria-hidden="true">
          <picture>
            <source srcSet={bodyHero} type="image/webp" />
            <img
              data-testid="fitsho-body-intelligence"
              src={bodyHeroFallback}
              alt=""
              width="1672"
              height="941"
              loading="lazy"
            />
          </picture>
          <span className="landing-body-interface__highlight" data-testid="fitsho-body-highlight" />
          <span className="landing-body-interface__line" />
          <div className="landing-callout landing-callout--intelligence">
            <span>{t("landing.callouts.shoulders")}</span>
            <strong>{t("landing.callouts.priority")}</strong>
          </div>
        </div>
        <div className="landing-section-heading">
          <p className="landing-kicker">{t("landing.intelligence.eyebrow")}</p>
          <h2 id="landing-intelligence-title" className="fitsho-display">{t("landing.intelligence.title")}</h2>
          <p>{t("landing.intelligence.body")}</p>
          <div className="landing-analysis-sample">
            <small>{t("landing.intelligence.sample")}</small>
            <dl>
              <div><dt>{t("landing.callouts.shoulders")}</dt><dd data-tone="priority">{t("landing.callouts.priority")}</dd></div>
              <div><dt>{t("landing.callouts.back")}</dt><dd>{t("landing.callouts.balanced")}</dd></div>
              <div><dt>{t("landing.intelligence.confidence")}</dt><dd>{t("landing.intelligence.medium")}</dd></div>
            </dl>
          </div>
        </div>
      </section>

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

function PlanBuilder({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation();

  return (
    <div
      className={`landing-builder${compact ? " landing-builder--compact" : ""}`}
      aria-label={t("landing.builder.label")}
    >
      <div className="landing-builder__heading">
        <span className="landing-builder__pulse" aria-hidden="true" />
        <div><strong>{t("landing.builder.title")}</strong><small>{t("landing.builder.body")}</small></div>
      </div>
      <ul>
        {(["structure", "exercise", "targets", "revision"] as const).map((item) => (
          <li key={item}><span aria-hidden="true">✓</span>{t(`landing.builder.items.${item}`)}</li>
        ))}
      </ul>
      <div className="landing-builder__summary">
        <span><small>{t("landing.callouts.training")}</small><strong>{t("landing.callouts.fourDays")}</strong></span>
        <span><small>{t("landing.callouts.nutrition")}</small><strong>{t("landing.callouts.calories")}</strong></span>
      </div>
      <span className="landing-builder__progress" aria-hidden="true"><i /></span>
    </div>
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
