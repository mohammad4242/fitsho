import { useTranslation } from "react-i18next";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "./AuthContext";

export function ProtectedRoute() {
  const { t } = useTranslation();
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <main className="loading-screen" aria-live="polite">
        <span className="loading-mark" aria-hidden="true" />
        <p>{t("common.loading")}</p>
      </main>
    );
  }

  if (user === null) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
