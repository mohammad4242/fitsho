import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export function AdminRoute() {
  const { user } = useAuth();

  if (user === null || !user.is_admin) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}
