import { type ReactNode, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";
import { verifyPhysicianAccess } from "../features/nutrition/api";
import { useProfile } from "../features/profile/ProfileContext";
import { verifyCoachAccess } from "../features/workoutReviews/api";
import { LanguageSwitcher } from "../shared/LanguageSwitcher";
import { AppIcon, type IconName } from "../shared/AppIcon";
import "./more.css";

export function MorePage() {
  const { i18n } = useTranslation();
  const { user, logout } = useAuth();
  const { profile, productMode, status } = useProfile();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [isCoach, setIsCoach] = useState(false);
  const [isPhysician, setIsPhysician] = useState(false);
  const english = i18n.resolvedLanguage === "en";
  const l = (fa: string, en: string) => english ? en : fa;
  const hasTraining = productMode === undefined || productMode === null
    || productMode === "training" || productMode === "both";
  const hasNutrition = productMode === "nutrition" || productMode === "both";

  useEffect(() => {
    let active = true;
    void verifyCoachAccess()
      .then(() => { if (active) setIsCoach(true); })
      .catch(() => undefined);
    void verifyPhysicianAccess()
      .then(() => { if (active) setIsPhysician(true); })
      .catch(() => undefined);
    return () => { active = false; };
  }, []);

  if (user === null) return null;

  function handleLogout() {
    setBusy(true);
    setError(false);
    void logout()
      .then(() => navigate("/login", { replace: true }))
      .catch(() => setError(true))
      .finally(() => setBusy(false));
  }

  return (
    <main className="more-page fitsho-page">
      <div className="more-page__container">
        <header className="more-page__heading">
          <h1>{l("بیشتر", "More")}</h1>
        </header>

        <section className="more-profile-card" aria-label={l("خلاصه پروفایل", "Profile summary")}>
          <span className="more-profile-card__avatar" aria-hidden="true">
            {(profile?.display_name ?? user.email).slice(0, 1).toLocaleUpperCase()}
          </span>
          <div>
            <strong>{profile?.display_name ?? user.email}</strong>
            <span>{user.email}</span>
          </div>
          <Link to={status === "ready" ? "/profile" : "/onboarding"}>
            {status === "ready" ? l("پروفایل", "Profile") : l("تکمیل پروفایل", "Complete profile")}
          </Link>
        </section>

        <div className="more-page__grid">
          <MoreGroup title={l("محصول", "Product")}>
            {hasTraining && <MoreLink to="/exercises" icon="dumbbell" title={l("کتابخانه حرکات", "Exercise library")} subtitle={l("حرکت‌ها، اجرا و نکات ایمنی", "Exercises, execution, and safety notes")} />}
            {hasTraining && <MoreLink to="/body-progress" icon="body" title="Body Analysis" subtitle={l("جلسه‌ها و تحلیل‌های ثبت‌شده", "Saved sessions and analyses")} />}
            {hasNutrition && <MoreLink to="/food-catalogue" icon="nutrition" title={l("کاتالوگ مواد غذایی", "Food catalogue")} subtitle={l("مرجع سریع ارزش غذایی", "Fast nutrition reference")} />}
            {hasNutrition && <MoreLink to="/nutrition-tracking" icon="target" title={l("ثبت تغذیه", "Nutrition tracking")} subtitle={l("پیگیری ساده وضعیت روز", "Simple daily check-in")} />}
          </MoreGroup>

          <MoreGroup title={l("حساب", "Account")}>
            <MoreLink to="/profile" icon="profile" title={l("اطلاعات پروفایل", "Profile information")} subtitle={l("مشخصات و تنظیمات برنامه", "Details and plan preferences")} />
            <div className="more-language-row"><div><strong>{l("زبان", "Language")}</strong><span>{l("فارسی و English", "English and فارسی")}</span></div><LanguageSwitcher /></div>
          </MoreGroup>

          {(isCoach || isPhysician || user.is_admin) && (
            <MoreGroup title={l("فضاهای تخصصی", "Workspaces")}>
              {isCoach && <MoreLink to="/coach/workouts" icon="profile" title={l("فضای مربی", "Coach workspace")} />}
              {isPhysician && <MoreLink to="/physician/nutrition" icon="profile" title={l("فضای پزشک", "Physician workspace")} />}
              {user.is_admin && <MoreLink to="/admin/exercises" icon="settings" title={l("مدیریت حرکات", "Exercise administration")} />}
              {user.is_admin && <MoreLink to="/admin/training-program-templates" icon="dumbbell" title={l("کتابخانه برنامه‌های تمرینی", "Training program library")} />}
              {user.is_admin && <MoreLink to="/admin/nutrition-meals" icon="nutrition" title={l("کاتالوگ وعده‌های غذایی", "Nutrition meal catalogue")} />}
              {user.is_admin && <MoreLink to="/admin/nutrition-programs" icon="nutrition" title={l("کاتالوگ برنامه‌های غذایی", "Nutrition program catalogue")} />}
              {user.is_admin && <MoreLink to="/admin/nutrition-monitoring" icon="settings" title={l("پایش تغذیه", "Nutrition monitoring")} />}
            </MoreGroup>
          )}
        </div>

        {error && <p className="fitsho-status fitsho-status--danger" role="alert">{l("خروج انجام نشد. دوباره تلاش کن.", "Could not sign out. Try again.")}</p>}
        <button className="more-page__logout" type="button" disabled={busy} onClick={handleLogout}>
          {busy ? l("در حال خروج…", "Signing out…") : l("خروج از حساب", "Sign out")}
        </button>
      </div>
    </main>
  );
}

function MoreGroup({ title, children }: { title: string; children: ReactNode }) {
  return <section className="more-group" aria-label={title}><h2>{title}</h2><div>{children}</div></section>;
}

function MoreLink({ to, icon, title, subtitle }: { to: string; icon: IconName; title: string; subtitle?: string }) {
  return <Link className="more-row" to={to}><span className="more-row__icon"><AppIcon name={icon} /></span><span><strong>{title}</strong>{subtitle && <small>{subtitle}</small>}</span><AppIcon className="more-row__chevron" name="chevron" /></Link>;
}
