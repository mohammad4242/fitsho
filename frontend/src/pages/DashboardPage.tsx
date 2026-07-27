import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";
import { useProfile } from "../features/profile/ProfileContext";
import { AuthenticatedHeader } from "../shared/AuthenticatedHeader";

export function DashboardPage() {
  const { i18n, t } = useTranslation();
  const { user } = useAuth();
  const { profile } = useProfile();

  if (user === null || profile === null) {
    return null;
  }

  const locale = i18n.resolvedLanguage === "en" ? "en" : "fa-IR";
  const joinedAt = new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
  }).format(new Date(user.created_at));

  return (
    <main className="dashboard-shell">
      <AuthenticatedHeader />

      <div className="dashboard-grid">
        <section className="welcome-card">
          <div>
            <p className="eyebrow eyebrow--accent">{t("dashboard.eyebrow")}</p>
            <h1>{t("dashboard.greeting", { name: profile.display_name })}</h1>
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

        <Link className="next-step-card profile-card-link" to="/profile">
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
          <span className="coming-soon">{t("dashboard.editProfile")}</span>
        </Link>
      </div>
    </main>
  );
}
