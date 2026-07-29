import { Navigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { PublicLandingPage } from "./PublicLandingPage";

export function PublicLandingRoute() {
  const { loading, user } = useAuth();

  if (loading) {
    return <main className="landing-loading" aria-busy="true" />;
  }

  return user === null ? <PublicLandingPage /> : <Navigate to="/dashboard" replace />;
}
