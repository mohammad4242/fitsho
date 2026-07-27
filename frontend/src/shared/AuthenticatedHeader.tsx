import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";
import { LanguageSwitcher } from "./LanguageSwitcher";

export function AuthenticatedHeader() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

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
          <nav className="authenticated-nav" aria-label={t("header.navigation")}>
            <Link
              to="/dashboard"
              aria-current={location.pathname === "/dashboard" ? "page" : undefined}
            >
              {t("header.dashboard")}
            </Link>
            <Link
              to="/profile"
              aria-current={location.pathname === "/profile" ? "page" : undefined}
            >
              {t("header.profile")}
            </Link>
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
