import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AdminExercisesPage } from "./features/admin/AdminExercisesPage";
import { AdminExerciseNewPage } from "./features/admin/AdminExerciseNewPage";
import { AdminRoute } from "./features/admin/AdminRoute";
import { AuthProvider } from "./features/auth/AuthContext";
import { LoginPage } from "./features/auth/LoginPage";
import { ProtectedRoute } from "./features/auth/ProtectedRoute";
import { RegisterPage } from "./features/auth/RegisterPage";
import { ExerciseCatalogPage } from "./features/exercises/ExerciseCatalogPage";
import { ExerciseDetailPage } from "./features/exercises/ExerciseDetailPage";
import { OnboardingPage } from "./features/profile/OnboardingPage";
import { ProfilePage } from "./features/profile/ProfilePage";
import { ProfileProvider } from "./features/profile/ProfileContext";
import {
  CompletedProfileRoute,
  GuestRoute,
  OnboardingRoute,
} from "./features/profile/ProfileRouteGuards";
import { DashboardPage } from "./pages/DashboardPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<GuestRoute />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>
      <Route element={<ProtectedRoute />}>
        <Route element={<AdminRoute />}>
          <Route path="/admin/exercises" element={<AdminExercisesPage />} />
          <Route path="/admin/exercises/new" element={<AdminExerciseNewPage />} />
        </Route>
        <Route element={<OnboardingRoute />}>
          <Route path="/onboarding" element={<OnboardingPage />} />
        </Route>
        <Route element={<CompletedProfileRoute />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/exercises" element={<ExerciseCatalogPage />} />
          <Route path="/exercises/:slug" element={<ExerciseDetailPage />} />
        </Route>
      </Route>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ProfileProvider>
          <AppRoutes />
        </ProfileProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
