import { lazy, Suspense, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";

import { AdminRoute } from "./features/admin/AdminRoute";
import { AuthProvider } from "./features/auth/AuthContext";
import { ProtectedRoute } from "./features/auth/ProtectedRoute";
import { ProfileProvider } from "./features/profile/ProfileContext";
import { useProfile } from "./features/profile/ProfileContext";
import {
  CompletedProfileRoute,
  CoachRoute,
  GuestRoute,
  NutritionCapabilityRoute,
  OnboardingRoute,
  PhysicianRoute,
} from "./features/profile/ProfileRouteGuards";
import { AppShell } from "./shared/AppShell";

const AdminAiSettingsPage = lazy(() => import("./features/admin/AdminAiSettingsPage").then(({ AdminAiSettingsPage }) => ({ default: AdminAiSettingsPage })));
const AdminExerciseEditPage = lazy(() => import("./features/admin/AdminExerciseEditPage").then(({ AdminExerciseEditPage }) => ({ default: AdminExerciseEditPage })));
const AdminExerciseNewPage = lazy(() => import("./features/admin/AdminExerciseNewPage").then(({ AdminExerciseNewPage }) => ({ default: AdminExerciseNewPage })));
const AdminExercisesPage = lazy(() => import("./features/admin/AdminExercisesPage").then(({ AdminExercisesPage }) => ({ default: AdminExercisesPage })));
const AdminNutritionMonitoringPage = lazy(() => import("./features/admin/AdminNutritionMonitoringPage").then(({ AdminNutritionMonitoringPage }) => ({ default: AdminNutritionMonitoringPage })));
const AdminSupplementsPage = lazy(() => import("./features/admin/AdminSupplementsPage").then(({ AdminSupplementsPage }) => ({ default: AdminSupplementsPage })));
const AdminTrainingTemplateEditorPage = lazy(() => import("./features/admin/AdminTrainingTemplateEditorPage").then(({ AdminTrainingTemplateEditorPage }) => ({ default: AdminTrainingTemplateEditorPage })));
const AdminTrainingTemplatesPage = lazy(() => import("./features/admin/AdminTrainingTemplatesPage").then(({ AdminTrainingTemplatesPage }) => ({ default: AdminTrainingTemplatesPage })));
const BodyAnalysisResultPage = lazy(() => import("./features/bodyPhotos/BodyAnalysisResultPage").then(({ BodyAnalysisResultPage }) => ({ default: BodyAnalysisResultPage })));
const BodyPhotoWizard = lazy(() => import("./features/bodyPhotos/BodyPhotoWizard").then(({ BodyPhotoWizard }) => ({ default: BodyPhotoWizard })));
const BodyProgressPage = lazy(() => import("./features/bodyPhotos/BodyProgressPage").then(({ BodyProgressPage }) => ({ default: BodyProgressPage })));
const CoachWorkoutReviewPage = lazy(() => import("./features/workoutReviews/CoachWorkoutReviewPage").then(({ CoachWorkoutReviewPage }) => ({ default: CoachWorkoutReviewPage })));
const DashboardPage = lazy(() => import("./pages/DashboardPage").then(({ DashboardPage }) => ({ default: DashboardPage })));
const ExerciseCatalogPage = lazy(() => import("./features/exercises/ExerciseCatalogPage").then(({ ExerciseCatalogPage }) => ({ default: ExerciseCatalogPage })));
const ExerciseDetailPage = lazy(() => import("./features/exercises/ExerciseDetailPage").then(({ ExerciseDetailPage }) => ({ default: ExerciseDetailPage })));
const FoodCataloguePage = lazy(() => import("./features/nutrition/FoodCataloguePage").then(({ FoodCataloguePage }) => ({ default: FoodCataloguePage })));
const LoginPage = lazy(() => import("./features/auth/LoginPage").then(({ LoginPage }) => ({ default: LoginPage })));
const MorePage = lazy(() => import("./pages/MorePage").then(({ MorePage }) => ({ default: MorePage })));
const NutritionEstimatePage = lazy(() => import("./features/nutrition/NutritionEstimatePage").then(({ NutritionEstimatePage }) => ({ default: NutritionEstimatePage })));
const NutritionLabsPage = lazy(() => import("./features/nutrition/NutritionLabsPage").then(({ NutritionLabsPage }) => ({ default: NutritionLabsPage })));
const NutritionSupplementsPage = lazy(() => import("./features/nutrition/NutritionSupplementsPage").then(({ NutritionSupplementsPage }) => ({ default: NutritionSupplementsPage })));
const NutritionTrackingPage = lazy(() => import("./features/nutrition/NutritionTrackingPage").then(({ NutritionTrackingPage }) => ({ default: NutritionTrackingPage })));
const OnboardingPage = lazy(() => import("./features/profile/OnboardingPage").then(({ OnboardingPage }) => ({ default: OnboardingPage })));
const PhysicianNutritionReviewPage = lazy(() => import("./features/nutrition/PhysicianNutritionReviewPage").then(({ PhysicianNutritionReviewPage }) => ({ default: PhysicianNutritionReviewPage })));
const ProfilePage = lazy(() => import("./features/profile/ProfilePage").then(({ ProfilePage }) => ({ default: ProfilePage })));
const PublicLandingRoute = lazy(() => import("./features/landing/PublicLandingRoute").then(({ PublicLandingRoute }) => ({ default: PublicLandingRoute })));
const PublicOnboardingPage = lazy(() => import("./features/publicOnboarding/PublicOnboardingPage").then(({ PublicOnboardingPage }) => ({ default: PublicOnboardingPage })));
const RegisterPage = lazy(() => import("./features/auth/RegisterPage").then(({ RegisterPage }) => ({ default: RegisterPage })));
const WorkoutPlanPage = lazy(() => import("./features/workouts/WorkoutPlanPage").then(({ WorkoutPlanPage }) => ({ default: WorkoutPlanPage })));

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<GuestRoute />}>
        <Route path="/login" element={deferred(<LoginPage />)} />
        <Route path="/register" element={deferred(<RegisterPage />)} />
      </Route>
      <Route element={<ProtectedRoute />}>
        <Route element={<CoachRoute />}>
          <Route path="/coach/workouts" element={deferred(<CoachWorkoutReviewPage />)} />
        </Route>
        <Route element={<PhysicianRoute />}>
          <Route path="/physician/nutrition" element={deferred(<PhysicianNutritionReviewPage />)} />
        </Route>
        <Route element={<AdminRoute />}>
          <Route path="/admin/ai-settings" element={deferred(<AdminAiSettingsPage />)} />
          <Route path="/admin/training-program-templates" element={deferred(<AdminTrainingTemplatesPage />)} />
          <Route path="/admin/training-program-templates/new" element={deferred(<AdminTrainingTemplateEditorPage />)} />
          <Route path="/admin/training-program-templates/:templateId/edit" element={deferred(<AdminTrainingTemplateEditorPage />)} />
          <Route path="/admin/exercises" element={deferred(<AdminExercisesPage />)} />
          <Route path="/admin/exercises/new" element={deferred(<AdminExerciseNewPage />)} />
          <Route path="/admin/exercises/:exerciseId/edit" element={deferred(<AdminExerciseEditPage />)} />
          <Route path="/admin/nutrition-supplements" element={deferred(<AdminSupplementsPage />)} />
          <Route path="/admin/nutrition-monitoring" element={deferred(<AdminNutritionMonitoringPage />)} />
        </Route>
        <Route element={<OnboardingRoute />}>
          <Route path="/onboarding" element={deferred(<OnboardingPage />)} />
        </Route>
        <Route element={<CompletedProfileRoute />}>
          <Route element={<CompletedAppShellRoute />}>
            <Route path="/dashboard" element={deferred(<DashboardPage />)} />
            <Route path="/more" element={deferred(<MorePage />)} />
            <Route path="/profile" element={deferred(<ProfilePage />)} />
            <Route path="/nutrition-profile" element={<NutritionProfileRoute />} />
            <Route element={<NutritionCapabilityRoute />}>
              <Route path="/nutrition-estimate" element={deferred(<NutritionEstimatePage />)} />
              <Route path="/nutrition-tracking" element={deferred(<NutritionTrackingPage />)} />
              <Route path="/nutrition-labs" element={deferred(<NutritionLabsPage />)} />
              <Route path="/nutrition-supplements" element={deferred(<NutritionSupplementsPage />)} />
              <Route path="/food-catalogue" element={deferred(<FoodCataloguePage />)} />
            </Route>
            <Route path="/body-progress" element={deferred(<BodyProgressPage />)} />
            <Route path="/body-progress/new" element={deferred(<BodyPhotoWizard />)} />
            <Route path="/body-progress/:sessionId" element={deferred(<BodyAnalysisResultPage />)} />
            <Route path="/workout-plan" element={deferred(<WorkoutPlanRoute />)} />
            <Route path="/exercises" element={deferred(<ExerciseCatalogPage />)} />
            <Route path="/exercises/:slug" element={deferred(<ExerciseDetailPage />)} />
          </Route>
        </Route>
      </Route>
      <Route path="/" element={deferred(<PublicLandingRoute />)} />
      <Route path="/get-started" element={deferred(<PublicOnboardingPage />)} />
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

function NutritionProfileRoute() {
  return <Navigate to="/profile" replace />;
}

function deferred(element: ReactNode) {
  return <Suspense fallback={<RouteLoadingFallback />}>{element}</Suspense>;
}

function RouteLoadingFallback() {
  const { t } = useTranslation();

  return (
    <main className="route-loading" role="status" aria-live="polite" aria-busy="true">
      <span className="route-loading__indicator" aria-hidden="true" />
      <span>{t("common.loading")}</span>
    </main>
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
