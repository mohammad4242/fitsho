import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { HYDRATED_ACCOUNT_KEY } from "../publicOnboarding/onboardingDraft";
import { verifyPhysicianAccess } from "../nutrition/api";
import { verifyCoachAccess } from "../workoutReviews/api";
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

  return status === "missing" || status === "mode_selected" ? <Outlet /> : <Navigate to="/dashboard" replace />;
}

export function CompletedProfileRoute() {
  const { status, retryProfile } = useProfile();
  const startupState = profileStartupState(status, retryProfile);

  if (startupState !== null) {
    return startupState;
  }

  const hasJustHydratedAccount = sessionStorage.getItem(HYDRATED_ACCOUNT_KEY) === "true";
  return status === "missing" && !hasJustHydratedAccount
    ? <Navigate to="/onboarding" replace />
    : <Outlet />;
}

export function NutritionCapabilityRoute() {
  const { productMode } = useProfile();
  return productMode === "nutrition" || productMode === "both"
    ? <Outlet />
    : <Navigate to="/dashboard" replace />;
}

export function PhysicianRoute() {
  const [status, setStatus] = useState<"loading" | "authorized" | "denied">("loading");
  useEffect(() => {
    let active = true;
    void verifyPhysicianAccess()
      .then(() => { if (active) setStatus("authorized"); })
      .catch(() => { if (active) setStatus("denied"); });
    return () => { active = false; };
  }, []);
  if (status === "loading") return <StartupState error={false} onRetry={() => undefined} />;
  return status === "authorized" ? <Outlet /> : <Navigate to="/dashboard" replace />;
}

export function CoachRoute() {
  const [status, setStatus] = useState<"loading" | "authorized" | "denied">("loading");
  useEffect(() => {
    let active = true;
    void verifyCoachAccess()
      .then(() => { if (active) setStatus("authorized"); })
      .catch(() => { if (active) setStatus("denied"); });
    return () => { active = false; };
  }, []);
  if (status === "loading") return <StartupState error={false} onRetry={() => undefined} />;
  return status === "authorized" ? <Outlet /> : <Navigate to="/dashboard" replace />;
}
