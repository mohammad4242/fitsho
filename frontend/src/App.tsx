import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";

import { AdminExercisesPage } from "./features/admin/AdminExercisesPage";
import { AdminAiModelsPage } from "./features/admin/AdminAiModelsPage";
import { AdminExerciseEditPage } from "./features/admin/AdminExerciseEditPage";
import { AdminExerciseNewPage } from "./features/admin/AdminExerciseNewPage";
import { AdminTrainingTemplatesPage } from "./features/admin/AdminTrainingTemplatesPage";
import { AdminTrainingTemplateEditorPage } from "./features/admin/AdminTrainingTemplateEditorPage";
import { AdminRoute } from "./features/admin/AdminRoute";
import { AuthProvider } from "./features/auth/AuthContext";
import { LoginPage } from "./features/auth/LoginPage";
import { ProtectedRoute } from "./features/auth/ProtectedRoute";
import { RegisterPage } from "./features/auth/RegisterPage";
import { ExerciseCatalogPage } from "./features/exercises/ExerciseCatalogPage";
import { ExerciseDetailPage } from "./features/exercises/ExerciseDetailPage";
import { BodyPhotoWizard } from "./features/bodyPhotos/BodyPhotoWizard";
import { BodyProgressPage } from "./features/bodyPhotos/BodyProgressPage";
import { OnboardingPage } from "./features/profile/OnboardingPage";
import { ProfilePage } from "./features/profile/ProfilePage";
import { ProfileProvider } from "./features/profile/ProfileContext";
import { useProfile } from "./features/profile/ProfileContext";
import { WorkoutPlanPage } from "./features/workouts/WorkoutPlanPage";
import {
  CompletedProfileRoute,
  GuestRoute,
  OnboardingRoute,
} from "./features/profile/ProfileRouteGuards";
import { DashboardPage } from "./pages/DashboardPage";
import { PublicLandingRoute } from "./features/landing/PublicLandingRoute";
import { AppShell } from "./shared/AppShell";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<GuestRoute />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>
      <Route element={<ProtectedRoute />}>
        <Route element={<AdminRoute />}>
          <Route path="/admin/ai-models" element={<AdminAiModelsPage />} />
          <Route path="/admin/training-program-templates" element={<AdminTrainingTemplatesPage />} />
          <Route path="/admin/training-program-templates/new" element={<AdminTrainingTemplateEditorPage />} />
          <Route path="/admin/training-program-templates/:templateId/edit" element={<AdminTrainingTemplateEditorPage />} />
          <Route path="/admin/exercises" element={<AdminExercisesPage />} />
          <Route path="/admin/exercises/new" element={<AdminExerciseNewPage />} />
          <Route path="/admin/exercises/:exerciseId/edit" element={<AdminExerciseEditPage />} />
        </Route>
        <Route element={<OnboardingRoute />}>
          <Route path="/onboarding" element={<OnboardingPage />} />
        </Route>
        <Route element={<CompletedProfileRoute />}>
          <Route element={<CompletedAppShellRoute />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/body-progress" element={<BodyProgressPage />} />
            <Route path="/body-progress/new" element={<BodyPhotoWizard />} />
            <Route path="/workout-plan" element={<WorkoutPlanRoute />} />
            <Route path="/exercises" element={<ExerciseCatalogPage />} />
            <Route path="/exercises/:slug" element={<ExerciseDetailPage />} />
          </Route>
        </Route>
      </Route>
      <Route path="/" element={<PublicLandingRoute />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

function CompletedAppShellRoute() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

function WorkoutPlanRoute() {
  const { profile } = useProfile();
  return <WorkoutPlanPage planDurationWeeks={profile?.plan_duration_weeks ?? 4} />;
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
