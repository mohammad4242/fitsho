import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";
import { LanguageSwitcher } from "../shared/LanguageSwitcher";

export function DashboardPage() {
  const { i18n, t } = useTranslation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (user === null) {
    return null;
  }

  const locale = i18n.resolvedLanguage === "en" ? "en" : "fa-IR";
  const joinedAt = new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
  }).format(new Date(user.created_at));

  function handleLogout() {
    setBusy(true);
    setError(null);
    void logout()
      .then(
        () => navigate("/login", { replace: true }),
        () => setError(t("errors.generic")),
      )
      .finally(() => setBusy(false));
  }

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <a className="brand-mark brand-mark--dark" href="/">
          <span className="brand-mark__pulse" aria-hidden="true" />
          {t("common.brand")}
        </a>
        <div className="dashboard-header__actions">
          <LanguageSwitcher />
          <button
            className="logout-button"
            type="button"
            onClick={handleLogout}
            disabled={busy}
          >
            {busy ? t("dashboard.loggingOut") : t("dashboard.logout")}
          </button>
        </div>
      </header>

      <div className="dashboard-grid">
        <section className="welcome-card">
          <div>
            <p className="eyebrow eyebrow--accent">{t("dashboard.eyebrow")}</p>
            <h1>{t("dashboard.greeting")}</h1>
            <p className="welcome-card__intro">{t("dashboard.intro")}</p>
          </div>
          <div className="session-badge">
            <span className="session-badge__dot" aria-hidden="true" />
            <span>
              <small>{t("dashboard.session")}</small>
              {t("dashboard.sessionActive")}
            </span>
          </div>
        </section>

        <section className="account-card" aria-label={t("dashboard.emailLabel")}>
          <div className="account-card__icon" aria-hidden="true">
            @
          </div>
          <div>
            <p>{t("dashboard.emailLabel")}</p>
            <strong dir="ltr">{user.email}</strong>
          </div>
          <div className="account-card__date">
            <p>{t("dashboard.joinedLabel")}</p>
            <strong>{joinedAt}</strong>
          </div>
        </section>

        <section className="next-step-card">
          <div className="next-step-card__copy">
            <p className="eyebrow">{t("dashboard.nextEyebrow")}</p>
            <h2>{t("dashboard.nextTitle")}</h2>
            <p>{t("dashboard.nextBody")}</p>
          </div>
          <div className="next-step-card__visual" aria-hidden="true">
            <span className="profile-line profile-line--head" />
            <span className="profile-line profile-line--body" />
            <span className="profile-line profile-line--goal" />
          </div>
          <span className="coming-soon">{t("dashboard.comingSoon")}</span>
        </section>

        {error && (
          <p className="form-error dashboard-error" role="alert">
            {error}
          </p>
        )}
      </div>
    </main>
  );
}
