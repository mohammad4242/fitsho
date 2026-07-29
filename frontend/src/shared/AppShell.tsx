import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";

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

  return (
    <div className="app-shell">
      <div className="app-shell__content">{children}</div>
      <nav className="app-shell__nav" aria-label={t("header.primaryNavigation")}>
        {navigation.map((item) => (
          <NavLink
            className={({ isActive }) =>
              `app-shell__nav-link${isActive ? " app-shell__nav-link--active" : ""}`
            }
            end={item.to === "/dashboard"}
            key={item.to}
            to={item.to}
          >
            <span className={`app-shell__nav-icon app-shell__nav-icon--${item.icon}`} aria-hidden="true" />
            <span>{t(item.label)}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
