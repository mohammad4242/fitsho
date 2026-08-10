import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";

import { useOptionalProfile } from "../features/profile/ProfileContext";

type AppShellProps = {
  children: ReactNode;
};

const navigation = [
  { to: "/dashboard", label: "header.today", icon: "pulse" },
  { to: "/workout-plan", label: "header.plan", icon: "plan", capability: "training" },
  { to: "/exercises", label: "header.exercises", icon: "exercise", capability: "training" },
  { to: "/nutrition-estimate", label: "header.nutritionTargets", icon: "plan", capability: "nutrition" },
  { to: "/food-catalogue", label: "header.foodCatalogue", icon: "food", capability: "nutrition" },
  { to: "/profile", label: "header.profile", icon: "profile" },
] as const;

export function AppShell({ children }: AppShellProps) {
  const { i18n, t } = useTranslation();
  const [moreOpen, setMoreOpen] = useState(false);
  const profileContext = useOptionalProfile();
  const status = profileContext?.status ?? "ready";
  const productMode = profileContext?.productMode;
  const visibleNavigation = navigation.filter((item) =>
    !("capability" in item) || productMode === undefined || productMode === null
      || item.capability === "training" && (productMode === "training" || productMode === "both")
      || item.capability === "nutrition" && (productMode === "nutrition" || productMode === "both"),
  );
  const hasOverflowNavigation = visibleNavigation.length > 4;
  const primaryNavigation = hasOverflowNavigation ? visibleNavigation.slice(0, 4) : visibleNavigation;
  const overflowNavigation = hasOverflowNavigation ? visibleNavigation.slice(4) : [];

  function renderNavigationLink(item: (typeof navigation)[number]) {
    const isProfile = item.to === "/profile";
    const to = isProfile && status !== "ready" ? "/onboarding" : item.to;
    const label = isProfile && status !== "ready" ? "header.completeProfile" : item.label;

    return (
      <NavLink
        className={({ isActive }) =>
          `app-shell__nav-link${isActive ? " app-shell__nav-link--active" : ""}`
        }
        end={to === "/dashboard"}
        key={item.to}
        onClick={() => setMoreOpen(false)}
        to={to}
      >
        <span className={`app-shell__nav-icon app-shell__nav-icon--${item.icon}`} aria-hidden="true" />
        <span>{t(label)}</span>
      </NavLink>
    );
  }

  return (
    <div className="app-shell">
      <div className="app-shell__content">{children}</div>
      <nav className="app-shell__nav" aria-label={t("header.primaryNavigation")}>
        {primaryNavigation.map(renderNavigationLink)}
        {hasOverflowNavigation && (
          <div className="app-shell__more">
            <button
              className="app-shell__nav-link app-shell__more-button"
              type="button"
              aria-controls="app-shell-more-menu"
              aria-expanded={moreOpen}
              onClick={() => setMoreOpen((open) => !open)}
            >
              <span className="app-shell__nav-icon app-shell__nav-icon--more" aria-hidden="true" />
              <span>{i18n.resolvedLanguage === "en" ? "More" : "بیشتر"}</span>
            </button>
            {moreOpen && (
              <div className="app-shell__more-menu" id="app-shell-more-menu">
                {overflowNavigation.map(renderNavigationLink)}
              </div>
            )}
          </div>
        )}
      </nav>
    </div>
  );
}
