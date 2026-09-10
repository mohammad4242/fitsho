import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import { ApiError } from "../../shared/apiClient";
import type { WorkoutPlan } from "./types";

const api = vi.hoisted(() => ({
  deleteWorkoutPlan: vi.fn(),
  getActiveWorkoutPlan: vi.fn(),
  getWorkoutPlanHistory: vi.fn(),
  getWorkoutPlan: vi.fn(),
  generateWorkoutPlan: vi.fn(),
  downloadWorkoutPlanPdf: vi.fn(),
  recordExerciseReplacement: vi.fn(),
  getCurrentWeeklyCheckIn: vi.fn(),
  getCurrentCompletionFeedback: vi.fn(),
  getCurrentWorkoutCycle: vi.fn(),
  saveCurrentWeeklyCheckIn: vi.fn(),
}));
const profileApi = vi.hoisted(() => ({
  getProfile: vi.fn(),
  updateProfile: vi.fn(),
}));

vi.mock("./api", () => api);
vi.mock("../profile/api", () => profileApi);
vi.mock("../../shared/AuthenticatedHeader", () => ({
  AuthenticatedHeader: () => <header>Fitsho</header>,
}));

import { WorkoutPlanPage } from "./WorkoutPlanPage";

const plan: WorkoutPlan = {
  id: "018f0000-0000-7000-8000-000000000001",
  status: "active",
  created_at: "2026-07-28T10:00:00Z",
  activated_at: "2026-07-28T10:00:00Z",
  plan_duration_weeks: 4,
  generation_source: "internal_engine",
  is_stale: false,
  days: [
    {
      day_number: 1,
      title_en: "Full body",
      title_fa: "تمام بدن",
      estimated_duration_minutes: 45,
      exercises: [
        {
          id: "018f0000-0000-7000-8000-000000000011",
          order_index: 1,
          sets: 3,
          reps_min: 8,
          reps_max: 12,
          rest_seconds: 90,
          rir: 2,
          estimated_minutes: 8,
          notes_en: null,
          notes_fa: "کنترل‌شده حرکت کن.",
          alternatives: [
            {
              reason_en: "A no-equipment alternative.",
              reason_fa: "جایگزین بدون تجهیزات.",
              exercise: {
                id: "018f0000-0000-7000-8000-000000000003",
                slug: "push-up",
                name_en: "Push-Up",
                name_fa: "شنا سوئدی",
                content_type: "exercise",
                body_region: "upper_body",
                primary_muscle: "chest",
                muscle_focus: "mid_chest",
                labels: [],
                secondary_muscles: ["triceps"],
                equipment: ["bodyweight"],
                difficulty: "beginner",
                media_path: "/media/exercises/push-up.gif",
                media_type: "gif",
              },
            },
          ],
          exercise: {
            id: "018f0000-0000-7000-8000-000000000002",
            slug: "dumbbell-bench-press",
            name_en: "Dumbbell Bench Press",
            name_fa: "پرس سینه دمبل",
            content_type: "exercise",
            body_region: "upper_body",
            primary_muscle: "chest",
            muscle_focus: "mid_chest",
            labels: [],
            secondary_muscles: ["triceps"],
            equipment: ["dumbbell", "bench"],
            difficulty: "beginner",
            media_path: "/media/bench.gif",
            media_type: "gif",
          },
        },
      ],
    },
  ],
};

const pendingVersion = {
  id: "018f0000-0000-7000-8000-000000000099",
  status: "pending_review" as const,
  created_at: "2026-08-10T10:00:00Z",
  activated_at: null,
  is_active: false,
  coach_review: {
    state: "pending_coach_review" as const,
    coach_display_name: null,
    coach_note: null,
    approved_at: null,
  },
};

const pendingPlan: WorkoutPlan = {
  ...plan,
  id: pendingVersion.id,
  status: "pending_review",
  activated_at: null,
  ai_coach_program_explanation_fa: "توضیح هوش مصنوعی نسخه جدید",
  days: plan.days.map((day) => ({
    ...day,
    title_fa: "برنامه در انتظار تأیید",
    exercises: day.exercises.map((item) => ({
      ...item,
      exercise: {
        ...item.exercise,
        name_fa: "اسکوات در انتظار تأیید",
        slug: "pending-squat",
      },
    })),
  })),
  coach_review: {
    state: "pending_coach_review",
    coach_display_name: null,
    coach_note: null,
    approved_at: null,
  },
};

beforeEach(() => {
  api.deleteWorkoutPlan.mockReset();
  api.getActiveWorkoutPlan.mockReset();
  api.getWorkoutPlanHistory.mockReset();
  api.getWorkoutPlan.mockReset();
  api.generateWorkoutPlan.mockReset();
  api.downloadWorkoutPlanPdf.mockReset();
  api.recordExerciseReplacement.mockReset();
  api.getCurrentWeeklyCheckIn.mockReset();
  api.getCurrentCompletionFeedback.mockReset();
  api.getCurrentWorkoutCycle.mockReset();
  api.saveCurrentWeeklyCheckIn.mockReset();
  profileApi.getProfile.mockReset();
  profileApi.updateProfile.mockReset();
  api.getWorkoutPlanHistory.mockResolvedValue([]);
  api.deleteWorkoutPlan.mockResolvedValue(undefined);
  api.generateWorkoutPlan.mockResolvedValue({ plan, reused: false });
  api.downloadWorkoutPlanPdf.mockResolvedValue(
    new Blob(["%PDF-test"], { type: "application/pdf" }),
  );
  api.recordExerciseReplacement.mockResolvedValue({
    id: "018f0000-0000-7000-8000-000000000021",
    user_id: "018f0000-0000-7000-8000-000000000031",
    cycle_id: "018f0000-0000-7000-8000-000000000041",
    workout_plan_exercise_id: "018f0000-0000-7000-8000-000000000011",
    original_exercise_id: "018f0000-0000-7000-8000-000000000002",
    replacement_exercise_id: "018f0000-0000-7000-8000-000000000003",
    reason: "equipment_unavailable",
    scope: "this_time",
    week_number: 1,
    created_at: "2026-08-18T10:00:00Z",
  });
  api.getCurrentWeeklyCheckIn.mockResolvedValue(null);
  api.getCurrentCompletionFeedback.mockResolvedValue(null);
  api.getCurrentWorkoutCycle.mockResolvedValue({
    cycle_id: "018f0000-0000-7000-8000-000000000041",
    workout_plan_id: plan.id,
    started_at: "2026-08-18T10:00:00Z",
    duration_weeks: 4,
    status: "active",
    current_week: 1,
  });
  api.saveCurrentWeeklyCheckIn.mockResolvedValue(null);
  profileApi.getProfile.mockResolvedValue({ workout_generation_method: "fitsho_coach" });
  profileApi.updateProfile.mockResolvedValue({ workout_generation_method: "ai" });
});

afterEach(() => vi.restoreAllMocks());

function mockBrowserDownload() {
  const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:plan");
  const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  return { click, createObjectURL, revokeObjectURL };
}

it("places generation controls before the current workout program and persists both choices", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue({
    ...plan,
    coach_review: {
      state: "pending_coach_review",
      coach_display_name: null,
      coach_note: null,
      approved_at: null,
    },
  });
  const user = userEvent.setup();

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  const pageTitle = await screen.findByRole("heading", { name: "برنامه تمرینی من" });
  const coachStatus = await screen.findByText("در انتظار تایید مربی");
  const selector = screen.getByRole("group", { name: "چه کسی برنامه‌ات را بنویسد؟" });
  const controls = selector.closest(".workout-plan-controls");
  const updateButton = screen.getByRole("button", { name: "به‌روزرسانی برنامه" });
  const hero = pageTitle.closest("header");
  const context = document.querySelector(".workout-plan-context");
  const schedule = screen.getByRole("list", { name: "روزهای تمرین تو" });
  const coachBanner = coachStatus.closest("aside");
  expect(controls).not.toBeNull();
  expect(updateButton.closest(".workout-plan-controls")).toBe(controls);
  expect(hero).not.toBeNull();
  expect(context).not.toBeNull();
  expect(coachBanner).not.toBeNull();
  expect(controls!.compareDocumentPosition(hero!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(hero!.compareDocumentPosition(context!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(context!.compareDocumentPosition(coachBanner!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(coachBanner!.compareDocumentPosition(schedule) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(coachBanner!.compareDocumentPosition(selector) & Node.DOCUMENT_POSITION_FOLLOWING).toBeFalsy();

  const internalEngine = screen.getByRole("radio", { name: "موتور داخلی" });
  const ai = screen.getByRole("radio", { name: "هوش مصنوعی" });
  expect(internalEngine).toBeChecked();
  await user.click(ai);
  expect(profileApi.updateProfile).toHaveBeenCalledWith({ workout_generation_method: "ai" });
  await user.click(internalEngine);
  expect(profileApi.updateProfile).toHaveBeenLastCalledWith({ workout_generation_method: "fitsho_coach" });
});

it("uses the compact English generation labels", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  await i18n.changeLanguage("en");
  try {
    render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

    expect(await screen.findByRole("radio", { name: "Internal Engine" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "AI" })).toBeInTheDocument();
  } finally {
    await i18n.changeLanguage("fa");
  }
});

it("translates the core-preservation duration warning for members", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue({
    ...plan,
    warnings: ["SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE"],
  });

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  expect(await screen.findByText("برای حفظ اثربخشی برنامه، لطفاً زمان تمرین خود را کمی افزایش دهید.")).toBeInTheDocument();
});

it("renders sectioned Core exercises after the main workout block", async () => {
  const sectionedPlan = {
    ...plan,
    days: [
      {
        ...plan.days[0],
        exercises: [
          { ...plan.days[0].exercises[0], section: "main" as const },
          {
            ...plan.days[0].exercises[0],
            id: "018f0000-0000-7000-8000-000000000012",
            order_index: 2,
            sets: 2,
            section: "core" as const,
            alternatives: [],
            exercise: {
              ...plan.days[0].exercises[0].exercise,
              id: "018f0000-0000-7000-8000-000000000013",
              slug: "plank",
              name_en: "Plank",
              name_fa: "پلانک",
              primary_muscle: "abs",
            },
          },
        ],
      },
    ],
  };
  api.getActiveWorkoutPlan.mockResolvedValue(sectionedPlan);

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  const mainExercise = await screen.findByText("پرس سینه دمبل");
  const coreExercise = await screen.findByText("پلانک");
  const coreHeading = screen.getByRole("heading", { name: "Core" });

  expect(mainExercise.compareDocumentPosition(coreHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(coreHeading.compareDocumentPosition(coreExercise) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

it("places the locked end-of-cycle feedback between PDF and Body Analysis tools", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  const feedback = await screen.findByRole("button", { name: "بازخورد پایان دوره" });
  const pdf = screen.getByRole("button", { name: "دانلود PDF" });
  const body = screen.getByRole("link", { name: "Body Analysis" });
  expect(pdf.compareDocumentPosition(feedback) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(feedback.compareDocumentPosition(body) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

it("keeps the initial version visible while coach approval is pending", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue({
    ...plan,
    coach_review: {
      state: "pending_coach_review",
      coach_display_name: null,
      coach_note: null,
      approved_at: null,
    },
  });

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  const pendingStatus = await screen.findByText("در انتظار تایید مربی");
  expect(pendingStatus.closest("aside")).toHaveClass("workout-review-banner--pending");
  expect(pendingStatus.closest("aside")?.querySelector(".workout-review-indicator")).toBeInTheDocument();
  expect(screen.queryByText(/نسخه اولیه فعال است/)).not.toBeInTheDocument();
  expect(screen.getByText("پرس سینه دمبل")).toBeInTheDocument();
});

it("keeps the active plan usable while a newer plan awaits coach approval", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  api.getWorkoutPlanHistory.mockResolvedValue([pendingVersion]);
  api.getWorkoutPlan.mockResolvedValue(pendingPlan);

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  expect(await screen.findByText("این برنامه هنوز به تأیید مربی نرسیده است؛ فعلاً می‌توانی آن را اجرا کنی.")).toBeInTheDocument();
  expect(screen.getByText("پرس سینه دمبل")).toBeInTheDocument();
  expect(screen.getByText("اسکوات در انتظار تأیید")).toBeInTheDocument();
  expect(screen.getByText("توضیح هوش مصنوعی نسخه جدید")).toBeVisible();
  expect(screen.getByRole("heading", { name: "برنامه در انتظار تأیید" })).toBeInTheDocument();
  const activeSchedule = screen.getByRole("list", { name: "روزهای تمرین تو" });
  const pendingSchedule = screen.getByRole("list", { name: "برنامه در انتظار تأیید مربی" });
  expect(activeSchedule).toBeInTheDocument();
  expect(pendingSchedule).toBeInTheDocument();
  expect(activeSchedule.compareDocumentPosition(pendingSchedule) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(api.getWorkoutPlan).toHaveBeenCalledWith(pendingVersion.id);
});

it("shows the pending plan as executable when there is no active plan", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(null);
  api.getWorkoutPlanHistory.mockResolvedValue([pendingVersion]);
  api.getWorkoutPlan.mockResolvedValue(pendingPlan);
  const user = userEvent.setup();

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  expect(await screen.findByText("این برنامه هنوز به تأیید مربی نرسیده است؛ فعلاً می‌توانی آن را اجرا کنی.")).toBeInTheDocument();
  expect(screen.getByText("اسکوات در انتظار تأیید")).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "برنامه در انتظار تأیید مربی" })).toBeInTheDocument();
  const feedbackTrigger = await screen.findByRole("button", { name: "بازخورد پایان دوره" });
  expect(feedbackTrigger).toBeInTheDocument();
  await user.click(feedbackTrigger);
  expect(screen.getByText(/پس از تأیید مربی و اتمام دوره ۴ هفته‌ای/)).toBeVisible();
  expect(screen.queryByText("پرس سینه دمبل")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "ساخت برنامه" })).not.toBeInTheDocument();
});

it("renders the pending plan returned by generation with its review warning", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(null);
  api.getWorkoutPlanHistory
    .mockResolvedValueOnce([])
    .mockResolvedValueOnce([pendingVersion]);
  api.getWorkoutPlan.mockResolvedValue(pendingPlan);
  api.generateWorkoutPlan.mockResolvedValue({
    plan: { ...plan, status: "pending_review", activated_at: null },
    reused: false,
  });
  const user = userEvent.setup();

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  await user.click(await screen.findByRole("button", { name: "ساخت برنامه" }));

  expect(await screen.findByText("این برنامه هنوز به تأیید مربی نرسیده است؛ فعلاً می‌توانی آن را اجرا کنی.")).toBeInTheDocument();
  expect(screen.getByText("اسکوات در انتظار تأیید")).toBeInTheDocument();
  expect(screen.queryByText("پرس سینه دمبل")).not.toBeInTheDocument();
});

it("lets the member inspect old and coach-approved immutable versions", async () => {
  const approvedPlan: WorkoutPlan = {
    ...plan,
    id: "018f0000-0000-7000-8000-000000000010",
    coach_review: {
      state: "coach_approved",
      coach_display_name: "مربی سارا",
      coach_note: "فشار جلسه دوم کمتر شد.",
      approved_at: "2026-08-09T12:00:00Z",
    },
  };
  api.getActiveWorkoutPlan.mockResolvedValue(approvedPlan);
  api.getWorkoutPlanHistory.mockResolvedValue([
    {
      id: approvedPlan.id,
      status: "active",
      created_at: approvedPlan.created_at,
      activated_at: approvedPlan.activated_at,
      is_active: true,
      coach_review: approvedPlan.coach_review,
    },
    {
      id: plan.id,
      status: "superseded",
      created_at: plan.created_at,
      activated_at: plan.activated_at,
      is_active: false,
      coach_review: {
        state: "initial_generated",
        coach_display_name: null,
        coach_note: null,
        approved_at: null,
      },
    },
  ]);
  api.getWorkoutPlan.mockResolvedValue({ ...plan, status: "superseded" });
  const user = userEvent.setup();

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  const approvedStatus = await screen.findByText("تأییدشده توسط مربی سارا");
  expect(approvedStatus.closest("aside")).toHaveClass("workout-review-banner--approved");
  expect(approvedStatus.closest("aside")?.querySelector(".workout-review-indicator")).toHaveTextContent("✓");
  expect(screen.getByText("فشار جلسه دوم کمتر شد.")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /نسخه اولیه/ }));

  expect(api.getWorkoutPlan).toHaveBeenCalledWith(plan.id);
  expect(await screen.findByText("در حال مشاهده نسخه قبلی")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "به‌روزرسانی برنامه" })).not.toBeInTheDocument();
});

it("shows deletion only for an archived version, never for the active version", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  api.getWorkoutPlanHistory.mockResolvedValue([
    {
      id: plan.id,
      status: "active",
      created_at: plan.created_at,
      activated_at: plan.activated_at,
      is_active: true,
      coach_review: { state: "coach_approved", coach_display_name: "مربی", coach_note: null, approved_at: plan.activated_at },
    },
    {
      ...pendingVersion,
      id: "018f0000-0000-7000-8000-000000000098",
      status: "superseded",
      is_active: false,
      coach_review: { state: "initial_generated", coach_display_name: null, coach_note: null, approved_at: null },
    },
  ]);

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  expect(await screen.findByRole("button", { name: "حذف نسخه قدیمی برنامه" })).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: /نسخه تأیید مربی/ })).toHaveLength(1);
  expect(screen.getAllByRole("button", { name: "حذف نسخه قدیمی برنامه" })).toHaveLength(1);
});

it("does not delete an archived version when confirmation is cancelled", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  api.getWorkoutPlanHistory.mockResolvedValue([
    {
      id: plan.id,
      status: "active",
      created_at: plan.created_at,
      activated_at: plan.activated_at,
      is_active: true,
      coach_review: { state: "none", coach_display_name: null, coach_note: null, approved_at: null },
    },
    { ...pendingVersion, status: "superseded", coach_review: { ...pendingVersion.coach_review, state: "initial_generated" } },
  ]);
  vi.spyOn(window, "confirm").mockReturnValue(false);
  const user = userEvent.setup();
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  await user.click(await screen.findByRole("button", { name: "حذف نسخه قدیمی برنامه" }));

  expect(api.deleteWorkoutPlan).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "حذف نسخه قدیمی برنامه" })).toBeInTheDocument();
});

it("removes an archived version after successful deletion and refreshes member plans", async () => {
  const archivedVersion = { ...pendingVersion, status: "superseded" as const, coach_review: { ...pendingVersion.coach_review, state: "initial_generated" as const } };
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  api.getWorkoutPlanHistory
    .mockResolvedValueOnce([
      {
        id: plan.id,
        status: "active",
        created_at: plan.created_at,
        activated_at: plan.activated_at,
        is_active: true,
        coach_review: { state: "none", coach_display_name: null, coach_note: null, approved_at: null },
      },
      archivedVersion,
    ])
    .mockResolvedValueOnce([{ id: plan.id, status: "active", created_at: plan.created_at, activated_at: plan.activated_at, is_active: true, coach_review: { state: "none", coach_display_name: null, coach_note: null, approved_at: null } }]);
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const user = userEvent.setup();
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  await user.click(await screen.findByRole("button", { name: "حذف نسخه قدیمی برنامه" }));

  await waitFor(() => expect(api.deleteWorkoutPlan).toHaveBeenCalledWith(archivedVersion.id));
  await waitFor(() => expect(screen.queryByRole("button", { name: "حذف نسخه قدیمی برنامه" })).not.toBeInTheDocument());
  expect(api.getWorkoutPlanHistory).toHaveBeenCalledTimes(2);
});

it("returns to the active plan when deleting the historical version currently displayed", async () => {
  const archivedVersion = { ...pendingVersion, id: "018f0000-0000-7000-8000-000000000098", status: "superseded" as const, coach_review: { ...pendingVersion.coach_review, state: "initial_generated" as const } };
  const historicalPlan = { ...plan, id: archivedVersion.id, status: "superseded" as const };
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  api.getWorkoutPlanHistory
    .mockResolvedValueOnce([
      { id: plan.id, status: "active", created_at: plan.created_at, activated_at: plan.activated_at, is_active: true, coach_review: { state: "none", coach_display_name: null, coach_note: null, approved_at: null } },
      archivedVersion,
    ])
    .mockResolvedValueOnce([{ id: plan.id, status: "active", created_at: plan.created_at, activated_at: plan.activated_at, is_active: true, coach_review: { state: "none", coach_display_name: null, coach_note: null, approved_at: null } }]);
  api.getWorkoutPlan.mockResolvedValue(historicalPlan);
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const user = userEvent.setup();
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  const historicalVersionButton = (await screen.findAllByRole("button", { name: /نسخه اولیه/ }))[1];
  await user.click(historicalVersionButton);
  expect(await screen.findByText("در حال مشاهده نسخه قبلی")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "حذف نسخه قدیمی برنامه" }));

  await waitFor(() => expect(api.deleteWorkoutPlan).toHaveBeenCalledWith(archivedVersion.id));
  await waitFor(() => expect(screen.queryByText("در حال مشاهده نسخه قبلی")).not.toBeInTheDocument());
  expect(screen.getByText("پرس سینه دمبل")).toBeInTheDocument();
});

it("keeps a failed deletion visible and exposes a retryable error", async () => {
  const archivedVersion = { ...pendingVersion, status: "failed" as const, coach_review: { ...pendingVersion.coach_review, state: "initial_generated" as const } };
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  api.getWorkoutPlanHistory.mockResolvedValue([
    { id: plan.id, status: "active", created_at: plan.created_at, activated_at: plan.activated_at, is_active: true, coach_review: { state: "none", coach_display_name: null, coach_note: null, approved_at: null } },
    archivedVersion,
  ]);
  api.deleteWorkoutPlan.mockRejectedValue(new Error("delete failed"));
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const user = userEvent.setup();
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  const deleteButton = await screen.findByRole("button", { name: "حذف نسخه قدیمی برنامه" });
  await user.click(deleteButton);

  expect(await screen.findByRole("alert")).toHaveTextContent("حذف نسخه قدیمی برنامه انجام نشد؛ دوباره تلاش کن.");
  expect(screen.getByRole("button", { name: "حذف نسخه قدیمی برنامه" })).toBeEnabled();
});

it("shows the fixed start guide and a generate action when no plan exists", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(null);
  const user = userEvent.setup();
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  expect(await screen.findByRole("heading", { name: "برنامه تمرینی من" })).toHaveClass("fitsho-display");
  expect(screen.getByText("قبل از شروع")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "ساخت برنامه" }));

  expect(api.generateWorkoutPlan).toHaveBeenCalledOnce();
});

it("shows plan context without cinematic background media", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  expect(await screen.findByRole("region", { name: "خلاصه برنامه" })).toBeInTheDocument();
  expect(screen.getByText("۱ روز تمرین")).toBeInTheDocument();
  expect(screen.getByText("۴۵ دقیقه برای هر جلسه")).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "روزهای تمرین تو" })).toBeInTheDocument();
  expect(document.querySelector("video")).not.toBeInTheDocument();
  const schedule = screen.getByRole("list", { name: "روزهای تمرین تو" });
  const guidance = screen.getByText("قبل از شروع");
  expect(schedule.compareDocumentPosition(guidance) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

it("shows the internal engine as the displayed plan's pre-plan source", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue({ ...plan, generation_source: "internal_engine" });

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  const context = await screen.findByRole("region", { name: "خلاصه برنامه" });
  const sourceCell = context.children[1];
  expect(sourceCell).toHaveTextContent("پیش‌برنامه");
  expect(sourceCell).toHaveTextContent("موتور داخلی");
});

it("shows artificial intelligence as the displayed plan's pre-plan source", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue({ ...plan, generation_source: "ai" });

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  const context = await screen.findByRole("region", { name: "خلاصه برنامه" });
  const sourceCell = context.children[1];
  expect(sourceCell).toHaveTextContent("پیش‌برنامه");
  expect(sourceCell).toHaveTextContent("هوش مصنوعی");
});

it("uses plan provenance instead of the current profile generation preference", async () => {
  profileApi.getProfile.mockResolvedValue({ workout_generation_method: "ai" });
  api.getActiveWorkoutPlan.mockResolvedValue({ ...plan, generation_source: "internal_engine" });

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  const context = await screen.findByRole("region", { name: "خلاصه برنامه" });
  const sourceCell = context.children[1];
  expect(sourceCell).toHaveTextContent("موتور داخلی");
  expect(sourceCell).not.toHaveTextContent("هوش مصنوعی");
});

it("shows the rounded average duration for every session instead of a range", async () => {
  const averagePlan: WorkoutPlan = {
    ...plan,
    days: [
      { ...plan.days[0]!, day_number: 1, estimated_duration_minutes: 44 },
      { ...plan.days[0]!, day_number: 2, estimated_duration_minutes: 45 },
    ],
  };
  api.getActiveWorkoutPlan.mockResolvedValue(averagePlan);

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  expect(await screen.findByText("۴۵ دقیقه برای هر جلسه")).toBeInTheDocument();
  expect(screen.queryByText("۴۴ تا ۴۵ دقیقه")).not.toBeInTheDocument();
});

it("shows the active compact plan status", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  const status = await screen.findByText("فعال");
  expect(status.closest("strong")).toHaveClass("workout-plan-context__status--active");
});

it("shows pending when coach approval is still pending", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue({
    ...plan,
    coach_review: {
      state: "pending_coach_review",
      coach_display_name: null,
      coach_note: null,
      approved_at: null,
    },
  });

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  const status = await screen.findByText("در انتظار مربی");
  expect(status.closest("strong")).toHaveClass("workout-plan-context__status--pending");
});

it("shows inactive when an archived version is selected", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  api.getWorkoutPlanHistory.mockResolvedValue([
    {
      id: plan.id,
      status: "active",
      created_at: plan.created_at,
      activated_at: plan.activated_at,
      is_active: true,
      coach_review: {
        state: "coach_approved",
        coach_display_name: "مربی سارا",
        coach_note: null,
        approved_at: plan.activated_at,
      },
    },
    {
      ...pendingVersion,
      id: "018f0000-0000-7000-8000-000000000098",
      status: "superseded",
      is_active: false,
      coach_review: {
        state: "initial_generated",
        coach_display_name: null,
        coach_note: null,
        approved_at: null,
      },
    },
  ]);
  api.getWorkoutPlan.mockResolvedValue({ ...plan, id: "018f0000-0000-7000-8000-000000000098", status: "superseded" });
  const user = userEvent.setup();

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  await user.click(await screen.findByRole("button", { name: /نسخه اولیه/ }));
  const status = await screen.findByText("غیرفعال");
  expect(status.closest("strong")).toHaveClass("workout-plan-context__status--inactive");
});

it("shows pending status and summary data for a pending-only plan", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(null);
  api.getWorkoutPlanHistory.mockResolvedValue([pendingVersion]);
  api.getWorkoutPlan.mockResolvedValue(pendingPlan);

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  expect(await screen.findByText("در انتظار مربی")).toBeInTheDocument();
  expect(screen.getByText("۴۵ دقیقه برای هر جلسه")).toBeInTheDocument();
});

it("explains the generation cooldown instead of showing a generic failure", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(null);
  api.generateWorkoutPlan.mockRejectedValue(
    new ApiError(429, "Workout plan generation is cooling down"),
  );
  const user = userEvent.setup();
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  await screen.findByRole("button", { name: "ساخت برنامه" });
  await user.click(screen.getByRole("button", { name: "ساخت برنامه" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "لطفاً چند دقیقه دیگر دوباره تلاش کن.",
  );
  expect(screen.queryByRole("button", { name: "تلاش دوباره" })).not.toBeInTheDocument();
});

it.each([
  [
    "BODYWEIGHT_ONLY_LEVEL_NOT_SUPPORTED",
    "برنامه تمرین فقط با وزن بدن در حال حاضر برای سطح ماه اول و مبتدی ارائه می‌شود.",
  ],
  [
    "BODYWEIGHT_TEMPLATE_DAYS_NOT_SUPPORTED",
    "برنامه تمرین با وزن بدن در حال حاضر برای ۲، ۳ یا ۴ روز در هفته طراحی شده است.",
  ],
  [
    "BODYWEIGHT_PULL_UP_BAR_REQUIRED",
    "برای اجرای کامل این برنامه و تمرین عضلات پشت و زیربغل به میله بارفیکس نیاز دارید. میله بارفیکس را به تجهیزات اضافه کنید.",
  ],
  [
    "BODYWEIGHT_TEMPLATE_EXERCISE_UNAVAILABLE",
    "با محدودیت‌های فعلی شما یکی از حرکات این برنامه قابل اجرا یا ایمن نیست. تجهیزات و محدودیت‌های تمرینی خود را بررسی کنید.",
  ],
])("maps %s to a dedicated bodyweight message", async (code, message) => {
  api.getActiveWorkoutPlan.mockResolvedValue(null);
  api.generateWorkoutPlan.mockRejectedValue(new ApiError(422, "bodyweight failure", null, code));
  const user = userEvent.setup();
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  await user.click(await screen.findByRole("button", { name: "ساخت برنامه" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(message);
  expect(screen.queryByRole("button", { name: "تلاش دوباره" })).not.toBeInTheDocument();
});

it("renders the selected duration, exercise media, and exercise detail link", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  const user = userEvent.setup();
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={6} /></MemoryRouter>);

  expect(await screen.findByLabelText("دوره 6 هفته‌ای")).toBeInTheDocument();
  expect(screen.getByText("پرس سینه دمبل")).toBeInTheDocument();
  expect(screen.getAllByRole("img", { name: "نمایش حرکت پرس سینه دمبل" })[0]).toHaveAttribute(
    "src",
    "/media/bench.gif",
  );
  const workoutDay = screen.getByText("تمام بدن").closest("details")!;
  expect(workoutDay).not.toHaveAttribute("open");
  await user.click(screen.getByText("تمام بدن").closest("summary")!);
  expect(workoutDay).toHaveAttribute("open");
  expect(screen.getByRole("link", { name: "مشاهده جزئیات حرکت" })).toHaveAttribute(
    "href",
    "/exercises/dumbbell-bench-press",
  );
  const quickActions = screen.getByRole("group", { name: "ابزارهای برنامه" });
  expect(quickActions).toHaveClass("workout-quick-actions");
  expect(screen.getByRole("button", { name: "دانلود PDF" })).toBeEnabled();
  expect(screen.queryByRole("heading", { name: "بازخورد پایان دوره" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Body Analysis" })).toHaveAttribute(
    "href",
    "/body-progress",
  );
  expect(screen.getByText("حرکت جایگزین")).toBeInTheDocument();
  expect(screen.getByText("حرکت جایگزین")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "شنا سوئدی" })).not.toBeInTheDocument();
});

it("shows a clear instruction for adjacent superset exercises", async () => {
  const first = { ...plan.days[0]!.exercises[0]!, superset_group: "pair-a" };
  const second = {
    ...first,
    id: "018f0000-0000-7000-8000-000000000012",
    order_index: 2,
    alternatives: [],
    exercise: {
      ...first.exercise,
      id: "018f0000-0000-7000-8000-000000000004",
      slug: "dumbbell-row",
      name_en: "Dumbbell Row",
      name_fa: "زیربغل دمبل",
      primary_muscle: "back" as const,
    },
  };
  api.getActiveWorkoutPlan.mockResolvedValue({
    ...plan,
    days: [{ ...plan.days[0]!, exercises: [first, second] }],
  });

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  expect(
    await screen.findByText("این حرکت را بلافاصله با حرکت بعدی اجرا کن؛ سپس استراحت کن."),
  ).toBeInTheDocument();
  expect(screen.getAllByText("سوپرست")).toHaveLength(2);
});

it("renders an incomplete superset group as straight sets", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue({
    ...plan,
    days: [{
      ...plan.days[0]!,
      exercises: [{ ...plan.days[0]!.exercises[0]!, superset_group: "incomplete" }],
    }],
  });

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  expect(await screen.findByText("پرس سینه دمبل")).toBeInTheDocument();
  expect(screen.queryByText("سوپرست")).not.toBeInTheDocument();
  expect(
    screen.queryByText("این حرکت را بلافاصله با حرکت بعدی اجرا کن؛ سپس استراحت کن."),
  ).not.toBeInTheDocument();
});

it("asks for a reason, then shows only prescribed alternatives and scope before submitting", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  const user = userEvent.setup();
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  await user.click(await screen.findByText("تمام بدن"));
  await user.click(screen.getByText("حرکت جایگزین"));

  expect(screen.getByRole("button", { name: "تجهیزاتش را ندارم" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "با این حرکت راحت نیستم" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "درد یا ناراحتی دارم" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "فعلاً دستگاه/محل در دسترس نیست" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "این حرکت را دوست ندارم" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "دلیل دیگر" })).toBeInTheDocument();
  expect(screen.queryByText("شنا سوئدی")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "تجهیزاتش را ندارم" }));
  expect(screen.getByRole("button", { name: "شنا سوئدی" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "جایگزین خارج از لیست" })).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "شنا سوئدی" }));
  expect(screen.getByRole("button", { name: "فقط همین بار" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "از این به بعد" })).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "فقط همین بار" }));
  await waitFor(() => expect(api.recordExerciseReplacement).toHaveBeenCalledWith({
    workout_plan_exercise_id: "018f0000-0000-7000-8000-000000000011",
    replacement_exercise_id: "018f0000-0000-7000-8000-000000000003",
    reason: "equipment_unavailable",
    scope: "this_time",
  }));
  expect(await screen.findByText("جایگزین انتخاب‌شده: شنا سوئدی")).toBeInTheDocument();
});

it("submits the selected reason and persistent scope and shows an API error", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  api.recordExerciseReplacement.mockRejectedValue(new ApiError(422, "Replacement is not allowed"));
  const user = userEvent.setup();
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  await user.click(await screen.findByText("تمام بدن"));
  await user.click(screen.getByText("حرکت جایگزین"));
  await user.click(screen.getByRole("button", { name: "این حرکت را دوست ندارم" }));
  await user.click(screen.getByRole("button", { name: "شنا سوئدی" }));
  await user.click(screen.getByRole("button", { name: "از این به بعد" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("ثبت جایگزین انجام نشد");
  expect(api.recordExerciseReplacement).toHaveBeenCalledWith({
    workout_plan_exercise_id: "018f0000-0000-7000-8000-000000000011",
    replacement_exercise_id: "018f0000-0000-7000-8000-000000000003",
    reason: "dislike",
    scope: "persistent",
  });
});

it("downloads the displayed workout plan from the existing PDF button", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  const browserDownload = mockBrowserDownload();
  const user = userEvent.setup();
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  await user.click(await screen.findByRole("button", { name: "دانلود PDF" }));

  expect(api.downloadWorkoutPlanPdf).toHaveBeenCalledWith(plan.id);
  expect(browserDownload.createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
  expect(browserDownload.click).toHaveBeenCalledOnce();
  expect(browserDownload.revokeObjectURL).toHaveBeenCalledWith("blob:plan");
});

it("disables the existing PDF button while the file is loading", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  mockBrowserDownload();
  let resolveDownload: ((value: Blob) => void) | undefined;
  api.downloadWorkoutPlanPdf.mockReturnValue(
    new Promise((resolve) => {
      resolveDownload = resolve;
    }),
  );
  const user = userEvent.setup();
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  const button = await screen.findByRole("button", { name: "دانلود PDF" });
  await user.click(button);

  expect(button).toBeDisabled();
  expect(screen.getByText("در حال آماده‌سازی PDF…")).toBeInTheDocument();

  resolveDownload?.(new Blob(["pdf"], { type: "application/pdf" }));
  await waitFor(() => expect(button).toBeEnabled());
});

it("shows a retryable error when the PDF request fails", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  api.downloadWorkoutPlanPdf.mockRejectedValue(new Error("PDF unavailable"));
  const user = userEvent.setup();
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  const button = await screen.findByRole("button", { name: "دانلود PDF" });
  await user.click(button);

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "دانلود PDF انجام نشد. دوباره تلاش کن.",
  );
  expect(button).toBeEnabled();
});

it("downloads the historical plan currently displayed", async () => {
  const historicalPlan = { ...plan, id: "018f0000-0000-7000-8000-000000000099" };
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  api.getWorkoutPlanHistory.mockResolvedValue([
    {
      id: plan.id,
      status: "active",
      created_at: plan.created_at,
      activated_at: plan.activated_at,
      is_active: true,
      coach_review: { state: "none", coach_display_name: null, coach_note: null, approved_at: null },
    },
    {
      id: historicalPlan.id,
      status: "superseded",
      created_at: "2026-07-01T10:00:00Z",
      activated_at: "2026-07-01T10:00:00Z",
      is_active: false,
      coach_review: { state: "none", coach_display_name: null, coach_note: null, approved_at: null },
    },
  ]);
  api.getWorkoutPlan.mockResolvedValue(historicalPlan);
  mockBrowserDownload();
  const user = userEvent.setup();
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  await user.click(await screen.findByRole("button", { name: /نسخه اولیه.*۱۰ تیر ۱۴۰۵/ }));
  await screen.findByText("در حال مشاهده نسخه قبلی");
  await user.click(screen.getByRole("button", { name: "دانلود PDF" }));

  expect(api.downloadWorkoutPlanPdf).toHaveBeenCalledWith(historicalPlan.id);
});

it("warns when the plan used provisional body-analysis findings", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue({
    ...plan,
    body_analysis_provenance: {
      analysis_id: "analysis-1",
      result_version: 1,
      source: "ai_provisional",
      provisional: true,
    },
  });
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  expect(await screen.findByRole("alert")).toHaveTextContent(
    /تأیید هر دو متخصص نرسیده است/,
  );
});

it("shows a backend-reported stale plan without hiding its exercises", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue({ ...plan, is_stale: true });
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  expect(await screen.findByText("این برنامه دیگر با شرایط فعلی یا دورهٔ انتخاب‌شده هماهنگ نیست؛ هر وقت آماده بودی برنامه بعدی را بساز.")).toBeInTheDocument();
  expect(screen.getByText("پرس سینه دمبل")).toBeInTheDocument();
});

it("keeps a plan visible during regeneration and announces a reused plan", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  let resolveGeneration: ((value: { plan: WorkoutPlan; reused: boolean }) => void) | undefined;
  api.generateWorkoutPlan.mockReturnValue(
    new Promise((resolve) => {
      resolveGeneration = resolve;
    }),
  );
  const user = userEvent.setup();
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  await screen.findByText("پرس سینه دمبل");
  await user.click(screen.getByRole("button", { name: "به‌روزرسانی برنامه" }));
  expect(screen.getAllByText("در حال ساخت برنامه…").length).toBeGreaterThan(0);
  expect(screen.getByText("پرس سینه دمبل")).toBeInTheDocument();
  resolveGeneration?.({ plan, reused: true });

  expect(await screen.findByText("برنامه فعلی‌ات هنوز با شرایط فعلی هماهنگ است.")).toBeInTheDocument();
});

it("keeps the active plan visible and offers retry when generation fails", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(plan);
  api.generateWorkoutPlan.mockRejectedValueOnce(new Error("provider unavailable"));
  api.generateWorkoutPlan.mockResolvedValueOnce({ plan, reused: false });
  const user = userEvent.setup();
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  await screen.findByText("پرس سینه دمبل");
  await user.click(screen.getByRole("button", { name: "به‌روزرسانی برنامه" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "ساخت برنامه انجام نشد؛ برنامه فعلی حفظ شده است. دوباره تلاش کن.",
  );
  expect(screen.getByText("پرس سینه دمبل")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "تلاش دوباره" }));

  expect(api.generateWorkoutPlan).toHaveBeenCalledTimes(2);
});
