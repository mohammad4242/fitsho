import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("@tanstack/react-query", () => ({
  useMutation: jest.fn(),
  useQuery: jest.fn(),
  useQueryClient: jest.fn(),
}));
jest.mock("expo-router", () => ({
  useLocalSearchParams: jest.fn(),
  useRouter: jest.fn(),
}));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("../ui/rtl", () => ({ languageForDirection: jest.fn() }));
jest.mock("../platform/connectivity", () => ({
  connectivityMonitor: {
    getSnapshot: () => ({ status: "online" }),
    subscribe: jest.fn(() => jest.fn()),
  },
}));
jest.mock("../profile/profileApi", () => ({ createProfileApi: jest.fn() }));
jest.mock("./workoutApi", () => ({ createWorkoutPlanApi: jest.fn() }));
jest.mock("./workoutPdfStore", () => ({
  ExpoWorkoutPlanPdfStore: jest.fn().mockImplementation(() => ({
    get: jest.fn<() => Promise<null>>().mockResolvedValue(null),
    save: jest.fn(),
  })),
}));

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocalSearchParams, useRouter } from "expo-router";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { languageForDirection } from "../ui/rtl";
import { createProfileApi } from "../profile/profileApi";
import type { WorkoutPlan, WorkoutPlanExercise, WorkoutPlanVersionSummary } from "./workoutApi";
import { createWorkoutPlanApi } from "./workoutApi";
import { WorkoutPlansScreen } from "./WorkoutPlansScreen";

const mockPush = jest.fn();
const mockRequest = jest.fn();
const mockDownload = jest.fn();
const mockUseMutation = jest.mocked(useMutation);
const mockUseQuery = jest.mocked(useQuery);
const mockUseQueryClient = jest.mocked(useQueryClient);
const mockUseLocalSearchParams = jest.mocked(useLocalSearchParams);
const mockUseRouter = jest.mocked(useRouter);
const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockLanguageForDirection = jest.mocked(languageForDirection);
const mockCreateProfileApi = jest.mocked(createProfileApi);
const mockCreateWorkoutPlanApi = jest.mocked(createWorkoutPlanApi);
const mockMutate = jest.fn();
let mockActivePlan: WorkoutPlan | null = null;
let mockPlanById: WorkoutPlan | null = null;
let mockHistory: WorkoutPlanVersionSummary[] = [];
let mockCycle: unknown = null;

function queryResult<T>(data: T) {
  return {
    data,
    error: null,
    isError: false,
    isFetching: false,
    isPending: false,
    isStale: false,
  } as never;
}

function resolved<T>(value: T) {
  return jest.fn<() => Promise<T>>().mockResolvedValue(value);
}

function renderWorkoutPlans() {
  return render(
    <SafeAreaProvider initialMetrics={{
      frame: { height: 800, width: 390, x: 0, y: 0 },
      insets: { bottom: 0, left: 0, right: 0, top: 0 },
    }}>
      <WorkoutPlansScreen />
    </SafeAreaProvider>,
  );
}

beforeEach(() => {
  mockPush.mockClear();
  mockRequest.mockClear();
  mockDownload.mockClear();
  mockUseLocalSearchParams.mockReturnValue({} as never);
  mockUseRouter.mockReturnValue({ push: mockPush } as never);
  mockLanguageForDirection.mockReturnValue("fa");
  mockActivePlan = null;
  mockPlanById = null;
  mockHistory = [];
  mockCycle = null;
  mockMutate.mockClear();
  mockUseMobileAuth.mockReturnValue({
    download: mockDownload,
    request: mockRequest,
    status: "signed_in",
    user: { email: "member@example.com", id: "member-1" },
  } as never);
  mockUseQueryClient.mockReturnValue({ setQueryData: jest.fn() } as never);
  mockCreateProfileApi.mockReturnValue({
    getProfile: resolved({ workout_generation_method: "fitsho_coach" }),
    updateProfile: jest.fn(),
  } as never);
  mockCreateWorkoutPlanApi.mockReturnValue({
    generate: jest.fn(),
    get: jest.fn(),
    getActive: resolved(null),
    getHistory: resolved([]),
  } as never);
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[0] === "profile") return queryResult({ workout_generation_method: "fitsho_coach" });
    if (key[1] === "plans") return queryResult(mockHistory);
    if (key[1] === "current-cycle") return queryResult(mockCycle);
    if (key[1] === "weekly-check-in" || key[1] === "completion-feedback") return queryResult(null);
    if (key[1] === "plan" && key[2] === "active") return queryResult(mockActivePlan);
    if (key[1] === "plan") return queryResult(mockPlanById);
    return queryResult(null);
  });
  mockUseMutation.mockImplementation(() => ({ isPending: false, mutate: mockMutate }) as never);
});

test("renders the web-parity workout hierarchy and shared generation control", () => {
  renderWorkoutPlans();

  expect(screen.getByRole("header", { name: "برنامه تمرینی من" })).toBeTruthy();
  expect(screen.getByLabelText("۴ هفته")).toBeTruthy();
  expect(screen.getByTestId("segmented-control")).toBeTruthy();
  expect(screen.getByRole("radio", { name: "موتور داخلی" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "هوش مصنوعی" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "ساخت برنامه تمرینی" })).toBeTruthy();
});

test("keeps generation choices as native touch actions", () => {
  renderWorkoutPlans();

  fireEvent.press(screen.getByRole("radio", { name: "هوش مصنوعی" }));

  expect(screen.getByRole("radio", { name: "هوش مصنوعی" }).props.accessibilityState).toMatchObject({
    selected: true,
  });
});

test("keeps the update action enabled when a pending review version exists", () => {
  const exercise = makeExercise("exercise-1", "شنا", "Push-up");
  mockActivePlan = makePlan("active", [makePlanExercise("plan-exercise-1", exercise, [])]);
  mockHistory = [makeHistoryVersion("pending-plan")];
  mockPlanById = makePlan("pending_review", [makePlanExercise("plan-exercise-1", exercise, [])]);

  renderWorkoutPlans();

  const updateButton = screen.getByRole("button", { name: "به‌روزرسانی برنامه" });
  expect(updateButton.props.accessibilityState).toMatchObject({ disabled: false });

  fireEvent.press(updateButton);

  expect(mockMutate).toHaveBeenCalledTimes(1);
});

test("starts the existing replacement workflow from an executable exercise action", async () => {
  const original = makeExercise("exercise-1", "شنا", "Push-up");
  const alternative = makeExercise("alternative-1", "پرس سینه دمبل", "Dumbbell Bench Press");
  const item = makePlanExercise("plan-exercise-1", original, [makeAlternative(alternative)]);
  const plan = makePlan("active", [item]);
  mockActivePlan = plan;
  mockPlanById = plan;
  mockCycle = {
    cycle_id: "cycle-1",
    current_week: 1,
    duration_weeks: 4,
    started_at: "2026-09-01T00:00:00Z",
    status: "active",
    workout_plan_id: plan.id,
  };

  renderWorkoutPlans();

  expect(screen.getByRole("link", { name: "مشاهده جزئیات حرکت" })).toBeTruthy();
  const replacementAction = screen
    .getAllByRole("button", { name: "حرکت جایگزین" })
    .find((action) => action.props.accessibilityLabel === "حرکت جایگزین");
  expect(replacementAction).toBeDefined();
  if (replacementAction === undefined) return;

  fireEvent.press(replacementAction);
  await waitFor(() => expect(screen.getByText("دلیل تعویض")).toBeTruthy());
  fireEvent.press(screen.getByRole("button", { name: "تجهیزاتش را ندارم" }));
  fireEvent.press(screen.getByRole("button", { name: alternative.name_fa }));
  fireEvent.press(screen.getByRole("button", { name: "فقط همین بار" }));

  expect(mockMutate).toHaveBeenCalledWith({
    reason: "equipment_unavailable",
    replacement_exercise_id: alternative.id,
    scope: "this_time",
    workout_plan_exercise_id: item.id,
  });
});

test("shows pending-plan alternatives read-only without exposing replacement submission", () => {
  const original = makeExercise("exercise-1", "شنا", "Push-up");
  const alternative = makeExercise("alternative-1", "پرس سینه دمبل", "Dumbbell Bench Press");
  const item = makePlanExercise("plan-exercise-1", original, [makeAlternative(alternative)]);
  const plan = makePlan("pending_review", [item]);
  mockPlanById = plan;
  mockHistory = [makeHistoryVersion(plan.id)];

  renderWorkoutPlans();

  const replacementAction = screen
    .getAllByRole("button", { name: "حرکت جایگزین" })
    .find((action) => action.props.accessibilityLabel === "حرکت جایگزین");
  expect(replacementAction).toBeDefined();
  if (replacementAction === undefined) return;
  fireEvent.press(replacementAction);

  expect(screen.getByTestId("workout-read-only-alternatives")).toBeTruthy();
  expect(screen.getByRole("link", { name: alternative.name_fa })).toBeTruthy();
  expect(screen.getByText("برای تمرکز سینه")).toBeTruthy();
  expect(screen.queryByText("دلیل تعویض")).toBeNull();
  expect(screen.queryByRole("button", { name: "فقط همین بار" })).toBeNull();
  expect(mockMutate).not.toHaveBeenCalled();
});

test("does not invent a replacement action for an exercise without alternatives", () => {
  const original = makeExercise("exercise-1", "شنا", "Push-up");
  const item = makePlanExercise("plan-exercise-1", original, []);
  const plan = makePlan("pending_review", [item]);
  mockPlanById = plan;
  mockHistory = [makeHistoryVersion(plan.id)];

  renderWorkoutPlans();

  expect(screen.queryByRole("button", { name: "حرکت جایگزین" })).toBeNull();
});

function makeExercise(id: string, nameFa: string, nameEn: string): WorkoutPlanExercise["exercise"] {
  return {
    body_region: "upper_body",
    content_type: "exercise",
    difficulty: "beginner",
    equipment: ["bodyweight"],
    id,
    labels: [],
    media_path: `/media/${id}.gif`,
    media_type: "gif",
    muscle_focus: null,
    name_en: nameEn,
    name_fa: nameFa,
    primary_muscle: "chest",
    secondary_muscles: [],
    slug: id,
  };
}

function makeAlternative(exercise: WorkoutPlanExercise["exercise"]): WorkoutPlanExercise["alternatives"][number] {
  return {
    exercise,
    reason_en: "For chest focus",
    reason_fa: "برای تمرکز سینه",
  };
}

function makePlanExercise(
  id: string,
  exercise: WorkoutPlanExercise["exercise"],
  alternatives: WorkoutPlanExercise["alternatives"],
): WorkoutPlanExercise {
  return {
    alternatives,
    duration_max_seconds: null,
    duration_min_seconds: null,
    estimated_minutes: 8,
    exercise,
    id,
    load_guidance: "وزن بدن",
    notes_en: null,
    notes_fa: null,
    order_index: 1,
    prescription_mode: "reps",
    progression_rule: "legacy",
    reps_max: 12,
    reps_min: 8,
    rest_seconds: 60,
    rir: 2,
    section: "main",
    sets: 3,
    superset_group: null,
    warmup_sets: 0,
  };
}

function makePlan(status: "active" | "pending_review", exercises: WorkoutPlanExercise[]): WorkoutPlan {
  return {
    activated_at: status === "active" ? "2026-09-01T00:00:00Z" : null,
    coach_review: {
      approved_at: status === "active" ? "2026-09-01T00:00:00Z" : null,
      coach_display_name: status === "active" ? "مربی" : null,
      coach_note: null,
      state: status === "active" ? "coach_approved" : "pending_coach_review",
    },
    created_at: "2026-09-01T00:00:00Z",
    days: [{
      ai_coach_explanation_fa: null,
      day_number: 1,
      estimated_duration_minutes: 45,
      exercises,
      focus: "upper_body",
      main_exercise_count: exercises.length,
      supplemental_exercise_count: 0,
      title_en: "Upper body",
      title_fa: "بالاتنه",
      total_exercise_count: exercises.length,
    }],
    engine_version: "test",
    id: status === "active" ? "active-plan" : "pending-plan",
    is_stale: false,
    plan_duration_weeks: 4,
    primary_goal: "general_fitness",
    ruleset_version: "test",
    safety_status: "clear",
    seed: 1,
    status,
    training_status: "novice",
  };
}

function makeHistoryVersion(id: string): WorkoutPlanVersionSummary {
  return {
    activated_at: null,
    coach_review: {
      approved_at: null,
      coach_display_name: null,
      coach_note: null,
      state: "pending_coach_review",
    },
    created_at: "2026-09-01T00:00:00Z",
    id,
    is_active: false,
    status: "pending_review",
  };
}
