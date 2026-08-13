import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";
import { useOptionalProfile } from "../features/profile/ProfileContext";
import { verifyPhysicianAccess } from "../features/nutrition/api";
import { verifyCoachAccess } from "../features/workoutReviews/api";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { AppIcon } from "./AppIcon";
import "./authenticatedHeader.css";

export function AuthenticatedHeader() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const profileContext = useOptionalProfile();
  const status = profileContext?.status ?? "ready";
  const productMode = profileContext?.productMode;
  const hasTraining = productMode === undefined || productMode === null || productMode === "training" || productMode === "both";
  const hasNutrition = productMode === "nutrition" || productMode === "both";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [isCoach, setIsCoach] = useState(false);
  const [isPhysician, setIsPhysician] = useState(false);

  useEffect(() => {
    if (user === null) return;
    let active = true;
    void Promise.resolve(verifyCoachAccess())
      .then(() => { if (active) setIsCoach(true); })
      .catch(() => { if (active) setIsCoach(false); });
    return () => { active = false; };
  }, [user]);

  useEffect(() => {
    if (user === null) return;
    let active = true;
    void Promise.resolve(verifyPhysicianAccess())
      .then(() => { if (active) setIsPhysician(true); })
      .catch(() => { if (active) setIsPhysician(false); });
    return () => { active = false; };
  }, [user]);

  if (user === null) {
    return null;
  }

  function handleLogout() {
    setBusy(true);
    setError(false);
    void logout()
      .then(() => navigate("/login", { replace: true }))
      .catch(() => setError(true))
      .finally(() => setBusy(false));
  }

  const primaryNavigationCandidates = [
    {
      to: "/dashboard",
      label: t("header.dashboard"),
      active: location.pathname === "/dashboard",
      visible: true,
    },
    {
      to: "/workout-plan",
      label: t("header.workoutPlan"),
      active: location.pathname.startsWith("/workout-plan"),
      visible: hasTraining,
    },
    {
      to: "/exercises",
      label: t("header.exercises"),
      active: location.pathname.startsWith("/exercises"),
      visible: hasTraining,
    },
    {
      to: "/nutrition-estimate",
      label: t("header.nutritionTargets"),
      active: location.pathname === "/nutrition-estimate",
      visible: hasNutrition,
    },
    {
      to: "/food-catalogue",
      label: t("header.foodCatalogue"),
      active: location.pathname === "/food-catalogue",
      visible: hasNutrition,
    },
    {
      to: "/body-progress",
      label: t("header.bodyProgress"),
      active: location.pathname.startsWith("/body-progress"),
      visible: hasTraining,
    },
    {
      to: status === "ready" ? "/profile" : "/onboarding",
      label: status === "ready" ? t("header.profile") : t("header.completeProfile"),
      active: location.pathname === "/profile" || location.pathname === "/onboarding",
      visible: true,
    },
  ].filter((item) => item.visible);
  const contextualNavigation = [
    { to: "/coach/workouts", label: t("header.coachWorkspace"), active: location.pathname.startsWith("/coach/workouts"), visible: isCoach },
    { to: "/physician/nutrition", label: t("header.physicianWorkspace"), active: location.pathname.startsWith("/physician/nutrition"), visible: isPhysician },
    { to: "/admin/exercises", label: t("header.adminExercises"), active: location.pathname.startsWith("/admin/exercises"), visible: user.is_admin },
    { to: "/admin/nutrition-monitoring", label: t("header.nutritionMonitoring"), active: location.pathname.startsWith("/admin/nutrition-monitoring"), visible: user.is_admin },
    { to: "/admin/nutrition-meals", label: t("header.adminMealCatalogue"), active: location.pathname.startsWith("/admin/nutrition-meals"), visible: user.is_admin },
    { to: "/admin/nutrition-programs", label: t("header.adminNutritionPrograms"), active: location.pathname.startsWith("/admin/nutrition-programs"), visible: user.is_admin },
    { to: "/admin/ai-settings", label: t("header.adminAiSettings"), active: location.pathname.startsWith("/admin/ai-settings"), visible: user.is_admin },
    { to: "/admin/training-program-templates", label: t("header.adminTrainingTemplates"), active: location.pathname.startsWith("/admin/training-program-templates"), visible: user.is_admin },
  ].find((item) => item.visible && item.active);
  const primaryNavigation = contextualNavigation
    ? [...primaryNavigationCandidates.slice(0, 3), contextualNavigation]
    : primaryNavigationCandidates.slice(0, 4);
  const isFa = i18n.language.startsWith("fa");
  const mobileContext = getMobileContext(location.pathname, t, isFa);
  const initial = (user.email?.trim().charAt(0) || t("common.brand").charAt(0)).toUpperCase();

  return (
    <>
      <header className={`dashboard-header${menuOpen ? " dashboard-header--menu-open" : ""}`}>
        <div className="authenticated-header__mobile">
          <div className="authenticated-header__context">
            {mobileContext.backTo ? (
              <Link className="authenticated-header__back" to={mobileContext.backTo} aria-label={isFa ? "بازگشت" : "Back"}>
                <AppIcon name="arrow" />
              </Link>
            ) : <span className="authenticated-header__pulse" aria-hidden="true" />}
            <span className="authenticated-header__title">{mobileContext.title}</span>
          </div>
          <Link className="authenticated-header__account" to="/more" aria-label={t("header.accountMenu")}>{initial}</Link>
        </div>
        <div className="authenticated-header__desktop">
          <Link className="brand-mark brand-mark--dark" to="/dashboard">
            <span className="brand-mark__pulse" aria-hidden="true" />
            {t("common.brand")}
          </Link>
          <div className="dashboard-header__actions">
          <div className="member-menu-wrap">
            <button
              className="member-menu-button"
              type="button"
              aria-label={menuOpen ? t("header.closeAccountMenu") : t("header.openAccountMenu")}
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((open) => !open)}
            >
              <span aria-hidden="true">☰</span>
            </button>
            {menuOpen && (
              <nav className="member-menu" aria-label={t("header.accountMenu")}>
                <div className="member-menu__group" role="group" aria-label={t("header.productLinks")}>
                  <span className="member-menu__section-label">{t("header.productLinks")}</span>
                  {hasTraining && <Link to="/workout-plan" onClick={() => setMenuOpen(false)}>{t("header.workoutPlan")}</Link>}
                  {hasTraining && <Link to="/exercises" onClick={() => setMenuOpen(false)}>{t("header.exercises")}</Link>}
                  {hasTraining && <Link to="/body-progress" onClick={() => setMenuOpen(false)}>{t("header.bodyProgress")}</Link>}
                  {hasNutrition && <Link to="/nutrition-estimate" onClick={() => setMenuOpen(false)}>{t("header.nutritionTargets")}</Link>}
                  {hasNutrition && <Link to="/food-catalogue" onClick={() => setMenuOpen(false)}>{t("header.foodCatalogue")}</Link>}
                  {isCoach && <Link to="/coach/workouts" onClick={() => setMenuOpen(false)}>{t("header.coachWorkspace")}</Link>}
                  {isPhysician && <Link to="/physician/nutrition" onClick={() => setMenuOpen(false)}>{t("header.physicianWorkspace")}</Link>}
                </div>
                <div className="member-menu__group" role="group" aria-label={t("header.accountLinks")}>
                  <span className="member-menu__section-label">{t("header.accountLinks")}</span>
                  <Link to={status === "ready" ? "/profile" : "/onboarding"} onClick={() => setMenuOpen(false)}>
                    {status === "ready" ? t("header.profile") : t("header.completeProfile")}
                  </Link>
                  <button type="button" disabled>{t("header.articles")} <small>{t("header.comingSoon")}</small></button>
                  <button className="member-menu__logout" type="button" onClick={handleLogout} disabled={busy}>
                    {busy ? t("header.loggingOut") : t("header.logout")}
                  </button>
                </div>
                <div className="member-menu__group member-menu__group--social" role="group" aria-label={t("header.socialNetworks")}>
                  <span className="member-menu__section-label">{t("header.socialNetworks")}</span>
                  <a href="https://instagram.com" target="_blank" rel="noreferrer">Instagram</a>
                  <a href="https://t.me" target="_blank" rel="noreferrer">Telegram</a>
                  <a href="https://facebook.com" target="_blank" rel="noreferrer">Facebook</a>
                  <a href="https://x.com" target="_blank" rel="noreferrer">X</a>
                </div>
                {user.is_admin && (
                  <div className="member-menu__group" role="group" aria-label={t("header.adminLinks")}>
                    <span className="member-menu__section-label">{t("header.adminLinks")}</span>
                    <Link to="/admin/exercises" onClick={() => setMenuOpen(false)}>{t("header.adminExercises")}</Link>
                    <Link to="/admin/nutrition-monitoring" onClick={() => setMenuOpen(false)}>{t("header.nutritionMonitoring")}</Link>
                    <Link to="/admin/nutrition-meals" onClick={() => setMenuOpen(false)}>{t("header.adminMealCatalogue")}</Link>
                    <Link to="/admin/nutrition-programs" onClick={() => setMenuOpen(false)}>{t("header.adminNutritionPrograms")}</Link>
                    <Link to="/admin/ai-settings" onClick={() => setMenuOpen(false)}>{t("header.adminAiSettings")}</Link>
                    <Link to="/admin/training-program-templates" onClick={() => setMenuOpen(false)}>{t("header.adminTrainingTemplates")}</Link>
                  </div>
                )}
              </nav>
            )}
          </div>
          <nav className="authenticated-nav" aria-label={t("header.navigation")}>
            {primaryNavigation.map((item) => (
              <Link key={item.to} to={item.to} aria-current={item.active ? "page" : undefined}>
                {item.label}
              </Link>
            ))}
          </nav>
          <LanguageSwitcher />
          <button
            className="logout-button"
            type="button"
            onClick={handleLogout}
            disabled={busy}
          >
            {busy ? t("header.loggingOut") : t("header.logout")}
          </button>
          </div>
        </div>
      </header>
      {error && (
        <p className="form-error authenticated-header__error" role="alert">
          {t("errors.generic")}
        </p>
      )}
    </>
  );
}

function getMobileContext(pathname: string, t: (key: string) => string, isFa: boolean): { title: string; backTo?: string } {
  const contexts: Array<{ prefix: string; title: string; backTo?: string }> = [
    { prefix: "/admin/nutrition-programs", title: t("header.adminNutritionPrograms"), backTo: "/more" },
    { prefix: "/admin/nutrition-meals", title: t("header.adminMealCatalogue"), backTo: "/more" },
    { prefix: "/nutrition-tracking", title: isFa ? "ثبت تغذیه" : "Nutrition tracking", backTo: "/nutrition-estimate" },
    { prefix: "/food-catalogue", title: t("header.foodCatalogue"), backTo: "/nutrition-estimate" },
    { prefix: "/nutrition-labs", title: isFa ? "آزمایش‌ها" : "Lab results", backTo: "/nutrition-estimate" },
    { prefix: "/nutrition-supplements", title: isFa ? "مکمل‌ها" : "Supplements", backTo: "/nutrition-estimate" },
    { prefix: "/exercises", title: t("header.exercises"), backTo: "/workout-plan" },
    { prefix: "/body-progress/", title: isFa ? "تحلیل بدن" : "Body analysis", backTo: "/body-progress" },
    { prefix: "/profile", title: t("header.profile"), backTo: "/more" },
    { prefix: "/dashboard", title: t("header.today") },
    { prefix: "/workout-plan", title: t("header.workoutPlan") },
    { prefix: "/nutrition-estimate", title: t("header.nutritionTargets") },
    { prefix: "/body-progress", title: t("header.bodyProgress") },
    { prefix: "/more", title: t("header.more") },
  ];
  return contexts.find((item) => pathname === item.prefix || pathname.startsWith(item.prefix))
    ?? { title: t("common.brand") };
}
