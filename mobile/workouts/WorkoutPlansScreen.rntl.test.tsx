import { fireEvent, render, screen, waitFor, within } from "@testing-library/react-native";
import { afterEach, beforeEach, expect, jest, test } from "@jest/globals";
import { Alert } from "react-native";
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
jest.mock("../ui/rtl", () => ({
  getRowDirectionStyle: (direction = "rtl") => ({ direction, flexDirection: "row" }),
  getTextDirectionStyle: (direction = "rtl", textAlign = direction === "rtl" ? "auto" : "left") => ({
    direction,
    textAlign,
    writingDirection: direction,
  }),
  languageForDirection: jest.fn(),
}));
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
const mockInvalidateQueries = jest.fn<() => Promise<undefined>>().mockResolvedValue(undefined);
const mockRemoveQueries = jest.fn();
const mockSetQueryData = jest.fn();
const mockDeletePlan = jest.fn<() => Promise<void>>();
let mockActivePlan: WorkoutPlan | null = null;
let mockPlanById: WorkoutPlan | null = null;
let mockHistory: WorkoutPlanVersionSummary[] = [];
let mockCycle: unknown = null;

type TestMutationOptions = {
  mutationFn?: (variables: unknown) => Promise<unknown>;
  mutationKey?: readonly unknown[];
  onError?: (error: unknown, variables: unknown) => void;
  onSettled?: () => void;
  onSuccess?: (data: unknown, variables: unknown) => void | Promise<void>;
};

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
  mockInvalidateQueries.mockClear();
  mockRemoveQueries.mockClear();
  mockSetQueryData.mockClear();
  mockDeletePlan.mockReset();
  mockDeletePlan.mockResolvedValue(undefined);
  mockUseMobileAuth.mockReturnValue({
    download: mockDownload,
    request: mockRequest,
    status: "signed_in",
    user: { email: "member@example.com", id: "member-1" },
  } as never);
  mockUseQueryClient.mockReturnValue({
    invalidateQueries: mockInvalidateQueries,
    removeQueries: mockRemoveQueries,
    setQueryData: mockSetQueryData,
  } as never);
  mockCreateProfileApi.mockReturnValue({
    getProfile: resolved({ workout_generation_method: "fitsho_coach" }),
    updateProfile: jest.fn(),
  } as never);
  mockCreateWorkoutPlanApi.mockReturnValue({
    deletePlan: mockDeletePlan,
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
  mockUseMutation.mockImplementation(((options: unknown) => {
    const mutationOptions = options as TestMutationOptions;
    if (mutationOptions.mutationKey?.[0] === "workout-plan-deletion") {
      return {
        isPending: false,
        mutate: (variables: unknown) => {
          mockMutate(variables);
          void Promise.resolve(mutationOptions.mutationFn?.(variables))
            .then((data) => mutationOptions.onSuccess?.(data, variables))
            .catch((error: unknown) => mutationOptions.onError?.(error, variables))
            .finally(() => mutationOptions.onSettled?.());
        },
      };
    }
    return { isPending: false, mutate: mockMutate };
  }) as never);
});

afterEach(() => {
  jest.restoreAllMocks();
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

  const controls = screen.getByTestId("workout-plan-controls");
  const updateButton = screen.getByRole("button", { name: "به‌روزرسانی برنامه" });
  expect(within(controls).getByTestId("segmented-control")).toBeTruthy();
  expect(within(controls).getByRole("button", { name: "به‌روزرسانی برنامه" })).toBe(updateButton);
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

test("exposes deletion for superseded history versions", () => {
  const exercise = makeExercise("exercise-1", "شنا", "Push-up");
  mockActivePlan = makePlan("active", [makePlanExercise("active-exercise", exercise, [])]);
  mockHistory = [makeHistoryVersion("active-plan", "active"), makeHistoryVersion("superseded-plan", "superseded")];

  renderWorkoutPlans();

  expect(screen.getByRole("button", { name: "حذف نسخه قدیمی برنامه" })).toBeTruthy();
});

test("does not expose deletion for active or pending history versions", () => {
  mockActivePlan = makePlan("active", []);
  mockHistory = [makeHistoryVersion("active-plan", "active"), makeHistoryVersion("pending-plan")];
  mockPlanById = makePlan("pending_review", []);

  renderWorkoutPlans();

  expect(screen.queryByRole("button", { name: "حذف نسخه قدیمی برنامه" })).toBeNull();
});

test("canceling old-plan deletion confirmation does nothing", () => {
  mockActivePlan = makePlan("active", []);
  mockHistory = [makeHistoryVersion("active-plan", "active"), makeHistoryVersion("superseded-plan", "superseded")];
  const alert = jest.spyOn(Alert, "alert").mockImplementation(() => undefined);
  renderWorkoutPlans();

  fireEvent.press(screen.getByRole("button", { name: "حذف نسخه قدیمی برنامه" }));

  expect(alert).toHaveBeenCalledWith(
    "حذف نسخه قدیمی",
    "این نسخه از تاریخچه برنامه‌های تمرینی شما حذف شود؟",
    expect.any(Array),
  );
  expect(mockMutate).not.toHaveBeenCalledWith("superseded-plan");
});

test("confirming old-plan deletion performs the mutation", () => {
  mockActivePlan = makePlan("active", []);
  mockHistory = [makeHistoryVersion("active-plan", "active"), makeHistoryVersion("superseded-plan", "superseded")];
  let actions: readonly { onPress?: () => void }[] = [];
  jest.spyOn(Alert, "alert").mockImplementation((_title, _message, buttons) => {
    actions = buttons ?? [];
  });
  renderWorkoutPlans();

  fireEvent.press(screen.getByRole("button", { name: "حذف نسخه قدیمی برنامه" }));
  actions[1]?.onPress?.();

  expect(mockMutate).toHaveBeenCalledWith("superseded-plan");
});

test("successful old-plan deletion refreshes history and removes the old version", async () => {
  const exercise = makeExercise("exercise-1", "شنا", "Push-up");
  mockActivePlan = makePlan("active", [makePlanExercise("active-exercise", exercise, [])]);
  mockHistory = [makeHistoryVersion("active-plan", "active"), makeHistoryVersion("superseded-plan", "superseded")];
  jest.spyOn(Alert, "alert").mockImplementation((_title, _message, buttons) => {
    buttons?.[1]?.onPress?.();
  });
  renderWorkoutPlans();

  fireEvent.press(screen.getByRole("button", { name: "حذف نسخه قدیمی برنامه" }));

  await waitFor(() => expect(mockDeletePlan).toHaveBeenCalledWith("superseded-plan"));
  expect(mockRemoveQueries).toHaveBeenCalledWith({ exact: true, queryKey: ["workouts", "plan", "superseded-plan"] });
  expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: ["workouts", "plans"] });
  expect(screen.queryByRole("button", { name: "حذف نسخه قدیمی برنامه" })).toBeNull();
});

test("deleting the selected historical version returns to the active plan", async () => {
  const exercise = makeExercise("exercise-1", "شنا", "Push-up");
  const oldExercise = makeExercise("old-exercise-1", "حرکت قدیمی", "Old exercise");
  mockActivePlan = makePlan("active", [makePlanExercise("active-exercise", exercise, [])]);
  mockPlanById = makePlan("superseded", [makePlanExercise("old-exercise", oldExercise, [])], "superseded-plan");
  mockHistory = [makeHistoryVersion("active-plan", "active"), makeHistoryVersion("superseded-plan", "superseded")];
  jest.spyOn(Alert, "alert").mockImplementation((_title, _message, buttons) => {
    buttons?.[1]?.onPress?.();
  });
  renderWorkoutPlans();

  fireEvent.press(screen.getAllByRole("button", { name: /نسخهٔ اولیه|نسخهٔ تأییدشده/ })[1]);
  fireEvent.press(screen.getByRole("button", { name: "حذف نسخه قدیمی برنامه" }));

  await waitFor(() => expect(mockDeletePlan).toHaveBeenCalledWith("superseded-plan"));
  await waitFor(() => expect(screen.queryByText("در حال مشاهده نسخه قبلی")).toBeNull());
  expect(screen.getByText("شنا")).toBeTruthy();
  expect(screen.queryByText("حرکت قدیمی")).toBeNull();
});

test("failed old-plan deletion keeps the version and shows a retry notice", async () => {
  mockActivePlan = makePlan("active", []);
  mockHistory = [makeHistoryVersion("active-plan", "active"), makeHistoryVersion("failed-plan", "failed")];
  mockDeletePlan.mockRejectedValue(new Error("delete failed"));
  jest.spyOn(Alert, "alert").mockImplementation((_title, _message, buttons) => {
    buttons?.[1]?.onPress?.();
  });
  renderWorkoutPlans();

  fireEvent.press(screen.getByRole("button", { name: "حذف نسخه قدیمی برنامه" }));

  await waitFor(() => expect(screen.getByText("حذف نسخه قدیمی برنامه انجام نشد؛ دوباره تلاش کن.")).toBeTruthy());
  expect(screen.getByRole("button", { name: "حذف نسخه قدیمی برنامه" })).toBeTruthy();
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

function makePlan(
  status: "active" | "pending_review" | "superseded" | "failed",
  exercises: WorkoutPlanExercise[],
  id = status === "active" ? "active-plan" : status === "pending_review" ? "pending-plan" : `${status}-plan`,
): WorkoutPlan {
  const active = status === "active";
  const pending = status === "pending_review";
  return {
    activated_at: active ? "2026-09-01T00:00:00Z" : null,
    coach_review: {
      approved_at: active ? "2026-09-01T00:00:00Z" : null,
      coach_display_name: active ? "مربی" : null,
      coach_note: null,
      state: active ? "coach_approved" : pending ? "pending_coach_review" : "initial_generated",
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
    id,
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

function makeHistoryVersion(
  id: string,
  status: "active" | "pending_review" | "superseded" | "failed" = "pending_review",
): WorkoutPlanVersionSummary {
  const active = status === "active";
  return {
    activated_at: active ? "2026-09-01T00:00:00Z" : null,
    coach_review: {
      approved_at: active ? "2026-09-01T00:00:00Z" : null,
      coach_display_name: active ? "مربی" : null,
      coach_note: null,
      state: active ? "coach_approved" : status === "pending_review" ? "pending_coach_review" : "initial_generated",
    },
    created_at: "2026-09-01T00:00:00Z",
    id,
    is_active: active,
    status,
  };
}
