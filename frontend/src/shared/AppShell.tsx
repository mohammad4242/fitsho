import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";

import { useOptionalProfile } from "../features/profile/ProfileContext";

type AppShellProps = {
  children: ReactNode;
};

const navigation = [
  { to: "/dashboard", label: "header.today", icon: "pulse" },
  { to: "/workout-plan", label: "header.plan", icon: "plan" },
  { to: "/exercises", label: "header.exercises", icon: "exercise" },
  { to: "/profile", label: "header.profile", icon: "profile" },
] as const;

export function AppShell({ children }: AppShellProps) {
  const { t } = useTranslation();
  const profileContext = useOptionalProfile();
  const status = profileContext?.status ?? "ready";

  return (
    <div className="app-shell">
      <div className="app-shell__content">{children}</div>
      <nav className="app-shell__nav" aria-label={t("header.primaryNavigation")}>
        {navigation.map((item) => {
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
            to={to}
          >
            <span className={`app-shell__nav-icon app-shell__nav-icon--${item.icon}`} aria-hidden="true" />
            <span>{t(label)}</span>
          </NavLink>
          );
        })}
      </nav>
    </div>
  );
}
