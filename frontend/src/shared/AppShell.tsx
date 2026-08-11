import { type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router-dom";

import { useOptionalProfile } from "../features/profile/ProfileContext";
import { AuthenticatedHeader } from "./AuthenticatedHeader";
import { AppIcon } from "./AppIcon";

type AppShellProps = {
  children: ReactNode;
};

const navigation = [
  { to: "/dashboard", label: "header.today", icon: "home" },
  { to: "/workout-plan", label: "header.plan", icon: "dumbbell", capability: "training" },
  { to: "/nutrition-estimate", label: "header.nutritionTargets", icon: "nutrition", capability: "nutrition" },
  { to: "/body-progress", label: "header.bodyProgress", icon: "progress", capability: "training" },
  { to: "/more", label: "header.more", icon: "more" },
] as const;

export function AppShell({ children }: AppShellProps) {
  const { t } = useTranslation();
  const location = useLocation();
  const productMode = useOptionalProfile()?.productMode;
  const visibleNavigation = navigation.filter((item) => (
    !("capability" in item)
    || productMode === undefined
    || productMode === null
    || item.capability === "training" && (productMode === "training" || productMode === "both")
    || item.capability === "nutrition" && (productMode === "nutrition" || productMode === "both")
  ));

  return (
    <div className="app-shell fitsho-app">
      <AuthenticatedHeader />
      <div className="app-shell__content">{children}</div>
      <nav className="app-shell__nav" aria-label={t("header.primaryNavigation")}>
        {visibleNavigation.map((item) => {
          const active = isPrimaryRouteActive(item.to, location.pathname);
          return (
            <Link
              aria-current={active ? "page" : undefined}
              className={`app-shell__nav-link${active ? " app-shell__nav-link--active" : ""}`}
              key={item.to}
              to={item.to}
            >
              <AppIcon className="app-shell__nav-icon" name={item.icon} />
              <span>{t(item.label)}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

function isMoreRoute(pathname: string) {
  return [
    "/more",
    "/profile",
  ].some((route) => pathname === route || pathname.startsWith(`${route}/`));
}

function isPrimaryRouteActive(route: string, pathname: string) {
  if (route === "/dashboard") return pathname === route;
  if (route === "/more") return isMoreRoute(pathname);
  if (route === "/workout-plan") {
    return ["/workout-plan", "/exercises"].some((item) => pathname === item || pathname.startsWith(`${item}/`));
  }
  if (route === "/nutrition-estimate") {
    return ["/nutrition-estimate", "/nutrition-tracking", "/food-catalogue", "/nutrition-labs", "/nutrition-supplements"]
      .some((item) => pathname === item || pathname.startsWith(`${item}/`));
  }
  return pathname === route || pathname.startsWith(`${route}/`);
}
