import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { LanguageSwitcher } from "../../shared/LanguageSwitcher";
import "./publicLanding.css";

const storySections = [
  {
    id: "purpose",
    eyebrow: "مربی همراه تو",
    title: "مسیر بهتر، هزینه کمتر.",
    body: "فیتشو تمرین و تغذیه را با هدف، زمان و بودجه واقعی تو هماهنگ می‌کند تا رسیدن به اندام دلخواهت کاربردی‌تر، قابل‌پیگیری‌تر و کم‌هزینه‌تر شود.",
  },
  {
    id: "momentum",
    eyebrow: "هر روز، یک قدم",
    title: "قرار نیست یک‌شبه تغییر کنی.",
    body: "بدن دلخواه نتیجه انتخاب‌های کوچکی است که هر روز تکرار می‌کنی. ما مسیر را روشن می‌کنیم؛ تو فقط قدم بعدی را بردار.",
  },
] as const;

const stores = ["Google Play", "کافه‌بازار", "App Store"] as const;
const socials = ["X / توییتر", "اینستاگرام", "تلگرام", "فیسبوک"] as const;

function useReducedMotion() {
  const [reducedMotion, setReducedMotion] = useState(
    () => typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(mediaQuery.matches);
    mediaQuery.addEventListener?.("change", update);
    return () => mediaQuery.removeEventListener?.("change", update);
  }, []);
  return reducedMotion;
}

export function PublicLandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const revealRefs = useRef<Array<HTMLElement | null>>([]);
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    if (reducedMotion || typeof IntersectionObserver === "undefined") {
      revealRefs.current.forEach((section) => section?.setAttribute("data-visible", "true"));
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) entry.target.setAttribute("data-visible", "true");
      });
    }, { threshold: 0.4 });
    revealRefs.current.forEach((section) => section && observer.observe(section));
    return () => observer.disconnect();
  }, [reducedMotion]);

  return (
    <main className={`public-landing ${videoFailed ? "has-video-fallback" : ""}`}>
      {!reducedMotion && (
        <video
          className="landing-film"
          data-testid="landing-film"
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
          aria-hidden="true"
          onError={() => setVideoFailed(true)}
        >
          <source src="/image&videos/film.mp4" type="video/mp4" />
        </video>
      )}
      <div className="landing-film-shade" aria-hidden="true" />

      <header className="landing-header">
        <button
          className="landing-menu-button"
          type="button"
          aria-label={menuOpen ? "بستن منو" : "باز کردن منو"}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span /><span /><span />
        </button>
        <Link className="brand-mark" to="/" aria-label="فیتشو">
          <span className="brand-mark__pulse" aria-hidden="true" />فیتشو
        </Link>
        <LanguageSwitcher />
      </header>

      {menuOpen && (
        <aside className="landing-menu" role="dialog" aria-label="منوی اصلی">
          <button type="button" aria-label="بستن منو" onClick={() => setMenuOpen(false)}>×</button>
          <nav>
            <a href="#about" onClick={() => setMenuOpen(false)}>درباره فیتشو</a>
            <a href="#download" onClick={() => setMenuOpen(false)}>دریافت اپ</a>
            <span>مقالات روز دنیا <small>به‌زودی</small></span>
            <Link to="/login">ورود اعضا</Link>
          </nav>
        </aside>
      )}

      <div className="landing-story">
        <section className="landing-panel landing-hero" data-visible="true">
          <div className="landing-panel__content">
            <p className="landing-kicker">FITSHO · TRAIN SMARTER</p>
            <h1 className="fitsho-display">بدن تو.<br />مسیر تو.</h1>
            <p>یک همراه هوشمند برای تمرین و تغذیه‌ای که با زندگی واقعی تو جور درمی‌آید.</p>
            <Link className="landing-primary-cta" to="/get-started">Get Started · شروع کن <span aria-hidden="true">←</span></Link>
          </div>
          <span className="landing-scroll-cue">برای ادامه اسکرول کن ↓</span>
        </section>

        {storySections.map((section, index) => (
          <section
            key={section.id}
            id={index === 0 ? "about" : section.id}
            ref={(node) => { revealRefs.current[index] = node; }}
            className="landing-panel landing-copy-panel"
          >
            <div className="landing-panel__content">
              <p className="landing-kicker">{section.eyebrow}</p>
              <h2 className="fitsho-display">{section.title}</h2>
              <p>{section.body}</p>
            </div>
          </section>
        ))}

        <section
          id="download"
          ref={(node) => { revealRefs.current[storySections.length] = node; }}
          className="landing-panel landing-download"
        >
          <div className="landing-panel__content">
            <p className="landing-kicker">همیشه همراهت</p>
            <h2 className="fitsho-display">فیتشو روی موبایل</h2>
            <p>نسخه‌های موبایل در راه‌اند. تا آن زمان نسخه وب کامل در دسترس توست.</p>
            <div className="store-list" aria-label="فروشگاه‌های اپلیکیشن">
              {stores.map((store) => <span key={store}><strong>{store}</strong><small>به‌زودی</small></span>)}
            </div>
          </div>
          <footer className="landing-footer">
            <span>© ۲۰۲۶ فیتشو</span>
            <nav aria-label="شبکه‌های اجتماعی">
              {socials.map((social) => <span key={social} title="لینک به‌زودی اضافه می‌شود">{social}</span>)}
            </nav>
          </footer>
        </section>
      </div>
    </main>
  );
}
