import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { LanguageSwitcher } from "../../shared/LanguageSwitcher";
import "./publicLanding.css";

type Brand = "google-play" | "cafe-bazaar" | "app-store" | "instagram" | "telegram" | "facebook" | "x";

const copy = {
  fa: {
    menu: { open: "باز کردن منو", close: "بستن منو", label: "منوی اصلی", about: "درباره فیتشو", download: "دریافت اپ", articles: "مقالات روز دنیا", signIn: "ورود اعضا" },
    hero: { title: <>بدن تو.<br />مسیر تو.</>, body: "یک همراه هوشمند برای تمرین و تغذیه‌ای که با زندگی واقعی تو جور درمی‌آید.", cta: "شروع کن" },
    story: [
      { id: "purpose", eyebrow: "مربی همراه تو", title: "مسیر بهتر، هزینه کمتر.", body: "فیتشو تمرین و تغذیه را با هدف، زمان و بودجه واقعی تو هماهنگ می‌کند تا رسیدن به اندام دلخواهت کاربردی‌تر، قابل‌پیگیری‌تر و کم‌هزینه‌تر شود." },
      { id: "momentum", eyebrow: "هر روز، یک قدم", title: "قرار نیست یک‌شبه تغییر کنی.", body: "بدن دلخواه نتیجه انتخاب‌های کوچکی است که هر روز تکرار می‌کنی. ما مسیر را روشن می‌کنیم؛ تو فقط قدم بعدی را بردار." },
    ],
    download: { eyebrow: "همیشه همراهت", title: "فیتشو روی موبایل", body: "نسخه‌های موبایل در راه‌اند. تا آن زمان نسخه وب کامل در دسترس توست.", label: "فروشگاه‌های اپلیکیشن", soon: "به‌زودی" },
    social: { label: "شبکه‌های اجتماعی", soon: "لینک به‌زودی اضافه می‌شود" },
  },
  en: {
    menu: { open: "Open menu", close: "Close menu", label: "Main menu", about: "About Fitsho", download: "Get the app", articles: "Global fitness articles", signIn: "Member sign in" },
    hero: { title: <>Your body.<br />Your path.</>, body: "A smart companion for training and nutrition that fits your real life.", cta: "Get started" },
    story: [
      { id: "purpose", eyebrow: "Your coach, alongside you", title: "A clearer path. A lighter cost.", body: "Fitsho aligns training and nutrition with your goal, time, and budget so progress toward your ideal physique feels practical, trackable, and affordable." },
      { id: "momentum", eyebrow: "One step, every day", title: "You do not have to change overnight.", body: "The body you want is built through small choices repeated daily. We make the next step clear; you take it." },
    ],
    download: { eyebrow: "Always with you", title: "Fitsho on mobile", body: "Our mobile apps are on their way. Until then, the complete web experience is ready for you.", label: "App stores", soon: "Coming soon" },
    social: { label: "Social media", soon: "Link coming soon" },
  },
} as const;

const stores: Array<{ id: Brand; fa: string; en: string }> = [
  { id: "google-play", fa: "Google Play", en: "Google Play" },
  { id: "cafe-bazaar", fa: "کافه‌بازار", en: "Cafe Bazaar" },
  { id: "app-store", fa: "App Store", en: "App Store" },
];

const socials: Array<{ id: Brand; fa: string; en: string }> = [
  { id: "instagram", fa: "اینستاگرام", en: "Instagram" },
  { id: "telegram", fa: "تلگرام", en: "Telegram" },
  { id: "facebook", fa: "فیسبوک", en: "Facebook" },
  { id: "x", fa: "ایکس / توییتر", en: "X" },
];

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

function BrandIcon({ brand, alt }: { brand: Brand; alt: string }) {
  return <img className="brand-icon" src={`/brand-icons/${brand}.svg`} alt={alt} />;
}

export function PublicLandingPage() {
  const { i18n } = useTranslation();
  const language = i18n.resolvedLanguage === "en" ? "en" : "fa";
  const text = copy[language];
  const [menuOpen, setMenuOpen] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const [socialVisible, setSocialVisible] = useState(false);
  const revealRefs = useRef<Array<HTMLElement | null>>([]);
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    if (reducedMotion || typeof IntersectionObserver === "undefined") {
      revealRefs.current.forEach((section) => section?.setAttribute("data-visible", "true"));
      setSocialVisible(true);
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) entry.target.setAttribute("data-visible", "true");
        if (entry.target.id === "download") setSocialVisible(entry.isIntersecting);
      });
    }, { threshold: 0.4 });
    revealRefs.current.forEach((section) => section && observer.observe(section));
    return () => observer.disconnect();
  }, [reducedMotion]);

  return (
    <main className={`public-landing ${videoFailed ? "has-video-fallback" : ""}`} data-language={language} dir={language === "fa" ? "rtl" : "ltr"}>
      {!reducedMotion && <video className="landing-film" data-testid="landing-film" autoPlay muted loop playsInline preload="metadata" aria-hidden="true" onError={() => setVideoFailed(true)}><source src="/image&videos/landing.mp4" type="video/mp4" /></video>}
      <div className="landing-film-shade" aria-hidden="true" />

      <header className="landing-header">
        <button className="landing-menu-button" type="button" aria-label={menuOpen ? text.menu.close : text.menu.open} aria-expanded={menuOpen} onClick={() => setMenuOpen((open) => !open)}><span /><span /><span /></button>
        <Link className="brand-mark" to="/" aria-label="Fitsho"><span className="brand-mark__pulse" aria-hidden="true" />Fitsho</Link>
        <LanguageSwitcher />
      </header>

      {menuOpen && <aside className="landing-menu" role="dialog" aria-label={text.menu.label}>
        <button type="button" aria-label={text.menu.close} onClick={() => setMenuOpen(false)}>×</button>
        <nav><a href="#about" onClick={() => setMenuOpen(false)}>{text.menu.about}</a><a href="#download" onClick={() => setMenuOpen(false)}>{text.menu.download}</a><span>{text.menu.articles} <small>{text.download.soon}</small></span><Link to="/login">{text.menu.signIn}</Link></nav>
      </aside>}

      <div className="landing-story">
        <section className="landing-panel landing-hero" data-visible="true"><div className="landing-panel__content"><p className="landing-kicker">FITSHO · TRAIN SMARTER</p><h1 className="fitsho-display">{text.hero.title}</h1><p>{text.hero.body}</p><Link className="landing-primary-cta" to="/get-started">{text.hero.cta}<span aria-hidden="true">{language === "fa" ? "←" : "→"}</span></Link></div></section>
        {text.story.map((section, index) => <section key={section.id} id={index === 0 ? "about" : section.id} ref={(node) => { revealRefs.current[index] = node; }} className="landing-panel landing-copy-panel"><div className="landing-panel__content"><p className="landing-kicker">{section.eyebrow}</p><h2 className="fitsho-display">{section.title}</h2><p>{section.body}</p></div></section>)}
        <section id="download" ref={(node) => { revealRefs.current[text.story.length] = node; }} className="landing-panel landing-download"><div className="landing-panel__content"><p className="landing-kicker">{text.download.eyebrow}</p><h2 className="fitsho-display">{text.download.title}</h2><p>{text.download.body}</p><div className="store-list" aria-label={text.download.label}>{stores.map((store) => <span key={store.id}><BrandIcon brand={store.id} alt={store.en} /><strong>{store[language]}</strong><small>{text.download.soon}</small></span>)}</div></div><footer className="landing-footer"><span>© 2026 Fitsho</span></footer></section>
      </div>
      {socialVisible && <nav className="landing-social-card landing-social-card--fixed" aria-label={text.social.label}>{socials.map((social) => <span className="landing-social-card__item" key={social.id} title={text.social.soon}><BrandIcon brand={social.id} alt={social.en} /><strong>{social[language]}</strong><small>{text.download.soon}</small></span>)}</nav>}
    </main>
  );
}
