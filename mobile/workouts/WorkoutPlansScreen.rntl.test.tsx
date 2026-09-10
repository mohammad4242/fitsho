import { fireEvent, render, screen, waitFor, within } from "@testing-library/react-native";
import { afterEach, beforeEach, expect, jest, test } from "@jest/globals";
import type { BinaryDownload } from "@fitician/core";
import { Alert, Linking } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

const mockPdfGet = jest.fn<() => Promise<StoredWorkoutPlanPdf | null>>();
const mockPdfSave = jest.fn<() => Promise<StoredWorkoutPlanPdf>>();
const mockDownloadPdf = jest.fn<() => Promise<BinaryDownload>>();

jest.mock("@tanstack/react-query", () => ({
  useMutation: jest.fn(),
  useQuery: jest.fn(),
  useQueryClient: jest.fn(),
}));
jest.mock("expo-router", () => ({
  useLocalSearchParams: jest.fn(),
  useRouter: jest.fn(),
  useIsFocused: jest.fn(() => true),
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
    get: mockPdfGet,
    save: mockPdfSave,
  })),
}));

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocalSearchParams, useRouter } from "expo-router";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { languageForDirection } from "../ui/rtl";
import { createProfileApi } from "../profile/profileApi";
import type { WorkoutPlan, WorkoutPlanExercise, WorkoutPlanVersionSummary } from "./workoutApi";
import { createWorkoutPlanApi } from "./workoutApi";
import type { StoredWorkoutPlanPdf } from "./workoutPdfStore";
import { WorkoutPlansScreen } from "./WorkoutPlansScreen";

const mockPush = jest.fn();
const mockRequest = jest.fn<() => Promise<unknown>>();
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
let mockPlansById: Record<string, WorkoutPlan> = {};
let mockHistory: WorkoutPlanVersionSummary[] = [];
let mockCycle: unknown = null;
let mockCompletionFeedback: unknown = null;
let mockProfileGenerationMethod: "fitsho_coach" | "ai" = "fitsho_coach";
let executeMutation = false;

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
    refetch: jest.fn<() => Promise<unknown>>().mockResolvedValue(undefined),
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
  mockPlansById = {};
  mockHistory = [];
  mockCycle = null;
  mockCompletionFeedback = null;
  mockProfileGenerationMethod = "fitsho_coach";
  executeMutation = false;
  mockPdfGet.mockReset();
  mockPdfGet.mockResolvedValue(null);
  mockPdfSave.mockReset();
  mockDownloadPdf.mockReset();
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
    getProfile: resolved({ workout_generation_method: mockProfileGenerationMethod }),
    updateProfile: jest.fn(),
  } as never);
  mockCreateWorkoutPlanApi.mockReturnValue({
    deletePlan: mockDeletePlan,
    downloadPdf: mockDownloadPdf,
    generate: jest.fn(),
    get: jest.fn(),
    getActive: resolved(null),
    getHistory: resolved([]),
  } as never);
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[0] === "profile") return queryResult({ workout_generation_method: mockProfileGenerationMethod });
    if (key[1] === "plans") return queryResult(mockHistory);
    if (key[1] === "current-cycle") return queryResult(mockCycle);
    if (key[1] === "weekly-check-in") return queryResult(null);
    if (key[1] === "completion-feedback") return queryResult(mockCompletionFeedback);
    if (key[1] === "plan" && key[2] === "active") return queryResult(mockActivePlan);
    if (key[1] === "plan") return queryResult(mockPlansById[String(key[2])] ?? mockPlanById);
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
    return {
      isPending: false,
      mutate: (variables: unknown) => {
        mockMutate(variables);
        if (!executeMutation) return;
        void Promise.resolve(mutationOptions.mutationFn?.(variables))
          .then((data) => mutationOptions.onSuccess?.(data, variables))
          .catch((error: unknown) => mutationOptions.onError?.(error, variables));
      },
    };
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

test("renders one compact RTL tools row and routes Body Analysis to its history", () => {
  mockActivePlan = makePlan("active", []);

  renderWorkoutPlans();

  const tools = screen.getByTestId("workout-plan-tools");
  const row = within(tools).getByTestId("workout-plan-tools-row");
  expect(within(tools).getByText("ابزارهای برنامه")).toBeTruthy();
  expect(within(row).getByText("دانلود PDF")).toBeTruthy();
  expect(within(row).getByText("بازخورد پایان دوره")).toBeTruthy();
  expect(within(row).getByText("Body Analysis")).toBeTruthy();
  expect(screen.queryByText("نسخهٔ PDF")).toBeNull();
  expect(screen.queryByText("ذخیرهٔ PDF برای استفاده آفلاین")).toBeNull();
  expect(screen.queryByRole("button", { name: "کتابخانه حرکات" })).toBeNull();

  fireEvent.press(within(row).getByRole("button", { name: "Body Analysis" }));
  expect(mockPush).toHaveBeenCalledWith("/member/body-analysis-history");
});

test("downloads, stores, and opens a workout PDF from the compact tool", async () => {
  const plan = makePlan("active", []);
  const download = {
    bytes: Uint8Array.from([37, 80, 68, 70]),
    contentType: "application/pdf",
    filename: "plan.pdf",
  };
  const stored = { byteSize: 4, fileName: "plan.pdf", planId: plan.id, uri: "file:///plan.pdf" };
  mockActivePlan = plan;
  mockDownloadPdf.mockResolvedValue(download);
  mockPdfSave.mockResolvedValue(stored);
  const openUrl = jest.spyOn(Linking, "openURL").mockResolvedValue(true);

  renderWorkoutPlans();
  fireEvent.press(await screen.findByRole("button", { name: "دانلود PDF" }));

  await waitFor(() => expect(mockDownloadPdf).toHaveBeenCalledWith(plan.id));
  expect(mockPdfSave).toHaveBeenCalledWith(plan.id, download);
  await waitFor(() => expect(openUrl).toHaveBeenCalledWith(stored.uri));
});

test("opens a valid stored workout PDF without downloading it again", async () => {
  const plan = makePlan("active", []);
  const stored = { byteSize: 4, fileName: "plan.pdf", planId: plan.id, uri: "file:///stored-plan.pdf" };
  mockActivePlan = plan;
  mockPdfGet.mockResolvedValue(stored);
  const openUrl = jest.spyOn(Linking, "openURL").mockResolvedValue(true);

  renderWorkoutPlans();
  fireEvent.press(await screen.findByRole("button", { name: "دانلود PDF" }));

  await waitFor(() => expect(openUrl).toHaveBeenCalledWith(stored.uri));
  expect(mockDownloadPdf).not.toHaveBeenCalled();
});

test("keeps the compact PDF tool disabled while downloading and shows a retryable error", async () => {
  const plan = makePlan("active", []);
  let resolveDownload: ((value: BinaryDownload) => void) | undefined;
  mockActivePlan = plan;
  mockDownloadPdf.mockReturnValue(new Promise((resolve) => {
    resolveDownload = resolve;
  }));

  renderWorkoutPlans();
  const button = await screen.findByRole("button", { name: "دانلود PDF" });
  fireEvent.press(button);

  expect(button.props.accessibilityState).toMatchObject({ busy: true, disabled: true });
  expect(screen.getByText("در حال آماده‌سازی PDF…")).toBeTruthy();
  resolveDownload?.({
    bytes: Uint8Array.from([37, 80, 68, 70]),
    contentType: "application/pdf",
    filename: "plan.pdf",
  });

  await waitFor(() => expect(button.props.accessibilityState).toMatchObject({ disabled: false }));

  mockDownloadPdf.mockRejectedValue(new Error("PDF unavailable"));
  fireEvent.press(button);
  expect(await screen.findByText("دانلود PDF انجام نشد. دوباره تلاش کن.")).toBeTruthy();
});

test("shows locked feedback compactly and expands the dynamic duration explanation", () => {
  const plan = { ...makePlan("active", []), plan_duration_weeks: 6 };
  mockActivePlan = plan;
  mockCycle = {
    cycle_id: "cycle-1",
    current_week: 3,
    duration_weeks: 6,
    started_at: "2026-09-01T00:00:00Z",
    status: "active",
    workout_plan_id: plan.id,
  };
  mockCompletionFeedback = {
    cycle_id: "cycle-1",
    current_week: 3,
    duration_weeks: 6,
    feedback: null,
    feedback_id: null,
    is_due: false,
    status: "active",
    submitted_at: null,
  };

  renderWorkoutPlans();

  const trigger = screen.getByRole("button", { name: "بازخورد پایان دوره" });
  expect(screen.queryByText(/این فرم بعد از پایان رسمی چرخه/)).toBeNull();
  fireEvent.press(trigger);
  expect(screen.getByText("پس از اتمام دوره ۶ هفته‌ای، این فرم برای هدفمندتر شدن برنامه بعدی فعال می‌شود. لطفاً فرم را کامل و با دقت پر کنید.")).toBeTruthy();
});

test("keeps feedback and the real pending-plan PDF available for a pending-only plan", async () => {
  const plan = makePlan("pending_review", [], "pending-plan");
  mockHistory = [makeHistoryVersion(plan.id)];
  mockPlanById = plan;

  renderWorkoutPlans();

  const tools = screen.getByTestId("workout-plan-tools");
  const pdf = within(tools).getByRole("button", { name: "دانلود PDF" });
  expect(pdf.props.accessibilityState).toMatchObject({ disabled: false });
  const trigger = within(tools).getByRole("button", { name: "بازخورد پایان دوره" });
  fireEvent.press(trigger);
  expect(screen.getByText("این برنامه هنوز به تأیید مربی نرسیده است. پس از تأیید مربی و اتمام دوره ۴ هفته‌ای، این فرم برای هدفمندتر شدن برنامه بعدی فعال می‌شود. لطفاً فرم را کامل و با دقت پر کنید.")).toBeTruthy();
  fireEvent.press(pdf);
  await waitFor(() => expect(mockDownloadPdf).toHaveBeenCalledWith(plan.id));
});

test("renders one pending foreground plan and swaps it for the selected archive", () => {
  const pendingExercise = makeExercise("pending-exercise", "حرکت جدید", "New movement");
  const archivedExercise = makeExercise("archived-exercise", "حرکت قدیمی", "Old movement");
  const pending = makePlan(
    "pending_review",
    [makePlanExercise("pending-row", pendingExercise, [])],
    "pending-plan",
  );
  pending.generation_source = "ai";
  const archived = makePlan(
    "superseded",
    [makePlanExercise("archived-row", archivedExercise, [])],
    "archived-plan",
  );
  mockHistory = [makeHistoryVersion(pending.id), makeHistoryVersion(archived.id, "superseded")];
  mockPlansById = { [pending.id]: pending, [archived.id]: archived };

  renderWorkoutPlans();

  expect(screen.getAllByText("برنامه تمرینی من")).toHaveLength(1);
  expect(screen.getByTestId("workout-plan-overview-pending-plan")).toBeTruthy();
  expect(screen.getByTestId("workout-plan-view-pending-plan")).toBeTruthy();
  expect(screen.getByLabelText("۴ هفته")).toBeTruthy();
  expect(screen.getByText("در انتظار تایید مربی")).toBeTruthy();
  expect(within(screen.getByLabelText("خلاصه برنامه")).getByText("هوش مصنوعی")).toBeTruthy();
  expect(screen.getByText("حرکت جدید")).toBeTruthy();
  expect(screen.queryByText("حرکت قدیمی")).toBeNull();
  expect(screen.getAllByTestId(/workout-plan-view-/)).toHaveLength(1);

  fireEvent.press(screen.getByRole("button", { name: "نسخهٔ اولیه" }));

  expect(screen.getByTestId("workout-plan-overview-archived-plan")).toBeTruthy();
  expect(screen.getByTestId("workout-plan-view-archived-plan")).toBeTruthy();
  expect(screen.getByText("غیرفعال")).toBeTruthy();
  expect(screen.getByText("در حال مشاهده نسخه قبلی")).toBeTruthy();
  expect(screen.getByText("حرکت قدیمی")).toBeTruthy();
  expect(screen.queryByText("حرکت جدید")).toBeNull();
  expect(screen.getAllByTestId(/workout-plan-view-/)).toHaveLength(1);
});

test("renders a complete pending-only plan when the active endpoint is empty", () => {
  const pending = makePlan("pending_review", [], "pending-only-plan");
  mockHistory = [makeHistoryVersion(pending.id)];
  mockPlansById = { [pending.id]: pending };

  renderWorkoutPlans();

  expect(screen.getByTestId("workout-plan-overview-pending-only-plan")).toBeTruthy();
  expect(screen.getByTestId("workout-plan-view-pending-only-plan")).toBeTruthy();
  expect(screen.getByText("برنامه تمرینی من")).toBeTruthy();
  expect(screen.getByText("در انتظار تایید مربی")).toBeTruthy();
  expect(screen.queryByText("هنوز برنامهٔ فعالی نداری")).toBeNull();
});

test("exposes the existing completion feedback form when the cycle is due", () => {
  const plan = makePlan("active", []);
  mockActivePlan = plan;
  mockCycle = {
    cycle_id: "cycle-1",
    current_week: 4,
    duration_weeks: 4,
    started_at: "2026-09-01T00:00:00Z",
    status: "active",
    workout_plan_id: plan.id,
  };
  mockCompletionFeedback = {
    cycle_id: "cycle-1",
    current_week: 4,
    duration_weeks: 4,
    feedback: null,
    feedback_id: null,
    is_due: true,
    status: "active",
    submitted_at: null,
  };

  renderWorkoutPlans();

  expect(screen.getByText("شدت کلی تمرین‌ها")).toBeTruthy();
  expect(screen.getByText("رضایت کلی")).toBeTruthy();
  expect(screen.getByRole("button", { name: "ثبت بازخورد" })).toBeTruthy();
});

test("submits due feedback through the existing saveCompletionFeedback API", async () => {
  const plan = makePlan("active", []);
  mockActivePlan = plan;
  mockCycle = {
    cycle_id: "cycle-1",
    current_week: 4,
    duration_weeks: 4,
    started_at: "2026-09-01T00:00:00Z",
    status: "active",
    workout_plan_id: plan.id,
  };
  mockCompletionFeedback = {
    cycle_id: "cycle-1",
    current_week: 4,
    duration_weeks: 4,
    feedback: null,
    feedback_id: null,
    is_due: true,
    status: "active",
    submitted_at: null,
  };
  mockRequest.mockResolvedValue(mockCompletionFeedback);
  executeMutation = true;

  renderWorkoutPlans();
  fireEvent.press(screen.getByRole("button", { name: "ثبت بازخورد" }));

  await waitFor(() => expect(mockRequest).toHaveBeenCalledWith({
    body: {
      energy_progress: "unchanged",
      endurance_progress: "unchanged",
      muscle_progress: "unchanged",
      note_optional: null,
      overall_difficulty: "appropriate",
      overall_recovery: "good",
      overall_satisfaction: "neutral",
      pain_or_limitation_feedback: null,
      performance_changes: null,
      strength_progress: "unchanged",
    },
    method: "PUT",
    path: "/api/v1/workout-cycles/current/completion-feedback",
  }));
});

test("renders the displayed plan's internal engine pre-plan source", () => {
  const plan = makePlan("active", [], "active-plan");
  plan.generation_source = "internal_engine";
  mockActivePlan = plan;
  mockPlanById = plan;

  renderWorkoutPlans();

  const context = screen.getByLabelText("خلاصه برنامه");
  expect(within(context).getByText("پیش‌برنامه")).toBeTruthy();
  expect(within(context).getByText("موتور داخلی")).toBeTruthy();
});

test("renders the displayed plan's artificial intelligence pre-plan source", () => {
  const plan = makePlan("active", [], "active-plan");
  plan.generation_source = "ai";
  mockActivePlan = plan;
  mockPlanById = plan;

  renderWorkoutPlans();

  const context = screen.getByLabelText("خلاصه برنامه");
  expect(within(context).getByText("پیش‌برنامه")).toBeTruthy();
  expect(within(context).getByText("هوش مصنوعی")).toBeTruthy();
});

test("uses displayed plan provenance instead of the current profile generation preference", () => {
  mockProfileGenerationMethod = "ai";
  const plan = makePlan("active", [], "active-plan");
  plan.generation_source = "internal_engine";
  mockActivePlan = plan;
  mockPlanById = plan;

  renderWorkoutPlans();

  const context = screen.getByLabelText("خلاصه برنامه");
  expect(within(context).getByText("موتور داخلی")).toBeTruthy();
  expect(within(context).queryByText("هوش مصنوعی")).toBeNull();
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

test("shows the generated pending replacement immediately instead of the old active plan", async () => {
  const oldExercise = makeExercise("old-exercise", "حرکت قبلی", "Old movement");
  const newExercise = makeExercise("new-exercise", "حرکت جدید", "New movement");
  const oldPlan = makePlan("active", [makePlanExercise("old-row", oldExercise, [])], "active-plan");
  const newPlan = makePlan("pending_review", [makePlanExercise("new-row", newExercise, [])], "pending-plan");
  mockActivePlan = oldPlan;
  mockHistory = [makeHistoryVersion(oldPlan.id, "active")];
  mockPlansById = { [newPlan.id]: newPlan };
  const generate = jest.fn().mockImplementation(async () => {
    mockActivePlan = null;
    mockHistory = [makeHistoryVersion(newPlan.id), makeHistoryVersion(oldPlan.id, "superseded")];
    return { plan: newPlan, reused: false };
  });
  mockCreateWorkoutPlanApi.mockReturnValue({
    deletePlan: mockDeletePlan,
    downloadPdf: mockDownloadPdf,
    generate,
    get: jest.fn(),
    getActive: resolved(null),
    getHistory: resolved(mockHistory),
  } as never);
  executeMutation = true;

  renderWorkoutPlans();
  fireEvent.press(screen.getByRole("button", { name: "به‌روزرسانی برنامه" }));

  expect(mockMutate).toHaveBeenCalledTimes(1);
  expect(generate).toHaveBeenCalledTimes(1);
  await waitFor(() => expect(screen.getByTestId("workout-plan-overview-pending-plan")).toBeTruthy());
  expect(screen.queryByText("حرکت قبلی")).toBeNull();
  expect(screen.getByText("حرکت جدید")).toBeTruthy();
  expect(screen.getAllByTestId(/workout-plan-view-/)).toHaveLength(1);
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

  fireEvent.press(screen.getAllByRole("button", { name: /نسخهٔ اولیه|نسخهٔ تأییدشده/ })[0]);
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
    generation_source: "internal_engine",
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
