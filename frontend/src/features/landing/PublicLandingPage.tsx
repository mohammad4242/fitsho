import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { LanguageSwitcher } from "../../shared/LanguageSwitcher";
import { LandingVideo } from "./LandingVideo";
import { landingScenes, type LandingScene } from "./landingContent";
import "./publicLanding.css";

function useReducedMotion() {
  const [reducedMotion, setReducedMotion] = useState(
    () =>
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;

    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updatePreference = () => setReducedMotion(mediaQuery.matches);

    mediaQuery.addEventListener?.("change", updatePreference);
    return () => mediaQuery.removeEventListener?.("change", updatePreference);
  }, []);

  return reducedMotion;
}

export function PublicLandingPage() {
  const [activeSceneId, setActiveSceneId] = useState<LandingScene["id"]>("strength");
  const sectionRefs = useRef<Array<HTMLElement | null>>([]);
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visibleEntry = entries.find((entry) => entry.isIntersecting);
        if (visibleEntry === undefined) return;

        const activeId = visibleEntry.target.id.replace("landing-", "") as LandingScene["id"];
        setActiveSceneId(activeId);
      },
      { threshold: 0.65 },
    );

    sectionRefs.current.forEach((section) => {
      if (section !== null) observer.observe(section);
    });

    return () => observer.disconnect();
  }, []);

  return (
    <main className="public-landing">
      <header className="landing-header">
        <Link className="brand-mark" to="/" aria-label="فیتشو">
          <span className="brand-mark__pulse" aria-hidden="true" />
          فیتشو
        </Link>
        <nav className="landing-header__actions" aria-label="ناوبری مهمان">
          <Link className="landing-login-link" to="/login">
            ورود
          </Link>
          <LanguageSwitcher />
        </nav>
      </header>

      <div className="landing-story">
        {landingScenes.map((scene, index) => {
          const isActive = activeSceneId === scene.id;
          const heading =
            index === 0 ? (
              <h1 className="landing-scene__title fitsho-display">{scene.title}</h1>
            ) : (
              <h2 className="landing-scene__title fitsho-display">{scene.title}</h2>
            );

          return (
            <section
              key={scene.id}
              id={`landing-${scene.id}`}
              ref={(section) => {
                sectionRefs.current[index] = section;
              }}
              className="landing-scene"
              data-active={isActive}
            >
              <LandingVideo scene={scene} active={isActive} reducedMotion={reducedMotion} />
              <div className="landing-scene__overlay" aria-hidden="true" />
              <div className="landing-scene__content">
                <p className="landing-scene__eyebrow">{scene.eyebrow}</p>
                {heading}
                <p className="landing-scene__body">{scene.body}</p>
                <Link className="landing-scene__cta" to="/register">
                  شروع رایگان
                </Link>
              </div>
            </section>
          );
        })}
      </div>
    </main>
  );
}
