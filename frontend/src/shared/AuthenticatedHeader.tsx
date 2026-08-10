import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";
import { useOptionalProfile } from "../features/profile/ProfileContext";
import { verifyPhysicianAccess } from "../features/nutrition/api";
import { verifyCoachAccess } from "../features/workoutReviews/api";
import { LanguageSwitcher } from "./LanguageSwitcher";

export function AuthenticatedHeader() {
  const { t } = useTranslation();
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

  return (
    <>
      <header className="dashboard-header">
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
                <Link
                  to={status === "ready" ? "/profile" : "/onboarding"}
                  onClick={() => setMenuOpen(false)}
                >
                  {status === "ready" ? t("header.profile") : t("header.completeProfile")}
                </Link>
                {hasTraining && <Link to="/workout-plan" onClick={() => setMenuOpen(false)}>
                  {t("header.workoutPlan")}
                </Link>}
                {hasTraining && <Link to="/exercises" onClick={() => setMenuOpen(false)}>
                  {t("header.exercises")}
                </Link>}
                {hasTraining && <Link to="/body-progress" onClick={() => setMenuOpen(false)}>
                  {t("header.bodyProgress")}
                </Link>}
                {isCoach && <Link to="/coach/workouts" onClick={() => setMenuOpen(false)}>
                  {t("header.coachWorkspace")}
                </Link>}
                {isPhysician && <Link to="/physician/nutrition" onClick={() => setMenuOpen(false)}>
                  {t("header.physicianWorkspace")}
                </Link>}
                {hasNutrition && <Link to="/nutrition-estimate" onClick={() => setMenuOpen(false)}>{t("header.nutritionTargets")}</Link>}
                {hasNutrition && <Link to="/food-catalogue" onClick={() => setMenuOpen(false)}>⌁ {t("header.foodCatalogue")}</Link>}
                <button type="button" disabled>
                  {t("header.articles")} <small>{t("header.comingSoon")}</small>
                </button>
                <span className="member-menu__section-label">{t("header.socialNetworks")}</span>
                <a href="https://instagram.com" target="_blank" rel="noreferrer">Instagram</a>
                <a href="https://t.me" target="_blank" rel="noreferrer">Telegram</a>
                <a href="https://facebook.com" target="_blank" rel="noreferrer">Facebook</a>
                <a href="https://x.com" target="_blank" rel="noreferrer">X</a>
                {user.is_admin && (
                  <><Link to="/admin/exercises" onClick={() => setMenuOpen(false)}>{t("header.adminExercises")}</Link><Link to="/admin/nutrition-monitoring" onClick={() => setMenuOpen(false)}>{t("header.nutritionMonitoring")}</Link></>
                )}
                <button className="member-menu__logout" type="button" onClick={handleLogout} disabled={busy}>
                  {busy ? t("header.loggingOut") : t("header.logout")}
                </button>
              </nav>
            )}
          </div>
          <nav className="authenticated-nav" aria-label={t("header.navigation")}>
            <Link
              to="/dashboard"
              aria-current={location.pathname === "/dashboard" ? "page" : undefined}
            >
              {t("header.dashboard")}
            </Link>
            {hasTraining && <Link
              to="/workout-plan"
              aria-current={location.pathname.startsWith("/workout-plan") ? "page" : undefined}
            >
              {t("header.workoutPlan")}
            </Link>}
            {isCoach && <Link
              to="/coach/workouts"
              aria-current={location.pathname.startsWith("/coach/workouts") ? "page" : undefined}
            >
              {t("header.coachWorkspace")}
            </Link>}
            {isPhysician && <Link
              to="/physician/nutrition"
              aria-current={location.pathname.startsWith("/physician/nutrition") ? "page" : undefined}
            >
              {t("header.physicianWorkspace")}
            </Link>}
            {hasTraining && <Link
              to="/exercises"
              aria-current={
                location.pathname.startsWith("/exercises") ? "page" : undefined
              }
            >
              {t("header.exercises")}
            </Link>}
            {hasTraining && <Link
              to="/body-progress"
              aria-current={location.pathname.startsWith("/body-progress") ? "page" : undefined}
            >
              {t("header.bodyProgress")}
            </Link>}
            {hasNutrition && <Link
              to="/nutrition-estimate"
              aria-current={location.pathname === "/nutrition-estimate" ? "page" : undefined}
            >{t("header.nutritionTargets")}</Link>}
            {hasNutrition && <Link
              to="/food-catalogue"
              aria-current={location.pathname === "/food-catalogue" ? "page" : undefined}
            >⌁ {t("header.foodCatalogue")}</Link>}
            <Link
              to={status === "ready" ? "/profile" : "/onboarding"}
              aria-current={location.pathname === "/profile" ? "page" : undefined}
            >
              {status === "ready" ? t("header.profile") : t("header.completeProfile")}
            </Link>
            {user.is_admin && (
              <>
                <Link
                  to="/admin/exercises"
                  aria-current={
                    location.pathname.startsWith("/admin/exercises") ? "page" : undefined
                  }
                >
                  {t("header.adminExercises")}
                </Link>
                <Link to="/admin/nutrition-monitoring">{t("header.nutritionMonitoring")}</Link>
                <Link
                  to="/admin/ai-settings"
                  aria-current={
                    location.pathname.startsWith("/admin/ai-settings") ? "page" : undefined
                  }
                >
                  {t("header.adminAiSettings")}
                </Link>
                <Link
                  to="/admin/training-program-templates"
                  aria-current={
                    location.pathname.startsWith("/admin/training-program-templates")
                      ? "page"
                      : undefined
                  }
                >
                  {t("header.adminTrainingTemplates")}
                </Link>
              </>
            )}
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
      </header>
      {error && (
        <p className="form-error authenticated-header__error" role="alert">
          {t("errors.generic")}
        </p>
      )}
    </>
  );
}
