import { useTranslation } from "react-i18next";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "./AuthContext";

export function ProtectedRoute() {
  const { t } = useTranslation();
  const { user, loading, startupError, retryStartup } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <main className="loading-screen" aria-live="polite">
        <span className="loading-mark" aria-hidden="true" />
        <p>{t("common.loading")}</p>
      </main>
    );
  }

  if (startupError) {
    return (
      <main className="loading-screen" role="alert">
        <p>{t("errors.network")}</p>
        <button className="retry-button" type="button" onClick={retryStartup}>
          {t("common.retry")}
        </button>
      </main>
    );
  }

  if (user === null) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
