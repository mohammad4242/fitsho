import { useTranslation } from "react-i18next";
import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { useProfile, type ProfileStatus } from "./ProfileContext";

function StartupState({
  error,
  onRetry,
}: {
  error: boolean;
  onRetry: () => void;
}) {
  const { t } = useTranslation();

  if (error) {
    return (
      <main className="loading-screen" role="alert">
        <p>{t("errors.network")}</p>
        <button className="retry-button" type="button" onClick={onRetry}>
          {t("common.retry")}
        </button>
      </main>
    );
  }

  return (
    <main className="loading-screen" aria-live="polite">
      <span className="loading-mark" aria-hidden="true" />
      <p>{t("common.loading")}</p>
    </main>
  );
}

function profileStartupState(status: ProfileStatus, retryProfile: () => void) {
  if (status === "idle" || status === "loading") {
    return <StartupState error={false} onRetry={retryProfile} />;
  }
  if (status === "error") {
    return <StartupState error onRetry={retryProfile} />;
  }
  return null;
}

export function GuestRoute() {
  const { user, loading, startupError, retryStartup } = useAuth();
  const { status, retryProfile } = useProfile();

  if (loading || startupError) {
    return <StartupState error={startupError} onRetry={retryStartup} />;
  }
  if (user === null) {
    return <Outlet />;
  }

  const startupState = profileStartupState(status, retryProfile);
  if (startupState !== null) {
    return startupState;
  }

  return <Navigate to={status === "missing" ? "/onboarding" : "/dashboard"} replace />;
}

export function OnboardingRoute() {
  const { status, retryProfile } = useProfile();
  const startupState = profileStartupState(status, retryProfile);

  if (startupState !== null) {
    return startupState;
  }

  return status === "missing" ? <Outlet /> : <Navigate to="/dashboard" replace />;
}

export function CompletedProfileRoute() {
  const { status, retryProfile } = useProfile();
  const startupState = profileStartupState(status, retryProfile);

  if (startupState !== null) {
    return startupState;
  }

  return status === "ready" ? <Outlet /> : <Navigate to="/onboarding" replace />;
}
