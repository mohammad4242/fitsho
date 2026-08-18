import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import { ApiError } from "../../shared/apiClient";
import type { WorkoutPlan } from "./types";

const api = vi.hoisted(() => ({
  getActiveWorkoutPlan: vi.fn(),
  getWorkoutPlanHistory: vi.fn(),
  getWorkoutPlan: vi.fn(),
  generateWorkoutPlan: vi.fn(),
  downloadWorkoutPlanPdf: vi.fn(),
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
  is_stale: false,
  days: [
    {
      day_number: 1,
      title_en: "Full body",
      title_fa: "تمام بدن",
      estimated_duration_minutes: 45,
      exercises: [
        {
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
  api.getActiveWorkoutPlan.mockReset();
  api.getWorkoutPlanHistory.mockReset();
  api.getWorkoutPlan.mockReset();
  api.generateWorkoutPlan.mockReset();
  api.downloadWorkoutPlanPdf.mockReset();
  profileApi.getProfile.mockReset();
  profileApi.updateProfile.mockReset();
  api.getWorkoutPlanHistory.mockResolvedValue([]);
  api.generateWorkoutPlan.mockResolvedValue({ plan, reused: false });
  api.downloadWorkoutPlanPdf.mockResolvedValue(
    new Blob(["%PDF-test"], { type: "application/pdf" }),
  );
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

it("places the compact generation selector between coach status and workout days and persists both choices", async () => {
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

  const coachStatus = await screen.findByText("در انتظار تایید مربی");
  const selector = screen.getByRole("group", { name: "چه کسی برنامه‌ات را بنویسد؟" });
  const schedule = screen.getByRole("list", { name: "روزهای تمرین تو" });
  const coachBanner = coachStatus.closest("aside");
  expect(coachBanner).not.toBeNull();
  expect(coachBanner!.compareDocumentPosition(selector) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(selector.compareDocumentPosition(schedule) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

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

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  expect(await screen.findByText("این برنامه هنوز به تأیید مربی نرسیده است؛ فعلاً می‌توانی آن را اجرا کنی.")).toBeInTheDocument();
  expect(screen.getByText("اسکوات در انتظار تأیید")).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "برنامه در انتظار تأیید مربی" })).toBeInTheDocument();
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

  expect(await screen.findByRole("region", { name: "خلاصه برنامه فعال" })).toBeInTheDocument();
  expect(screen.getByText("۱ روز تمرین")).toBeInTheDocument();
  expect(screen.getByText("۴۵ دقیقه برای هر جلسه")).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "روزهای تمرین تو" })).toBeInTheDocument();
  expect(document.querySelector("video")).not.toBeInTheDocument();
  const schedule = screen.getByRole("list", { name: "روزهای تمرین تو" });
  const guidance = screen.getByText("قبل از شروع");
  expect(schedule.compareDocumentPosition(guidance) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
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
  expect(screen.getByRole("button", { name: "بازخورد پایان دوره" })).toBeDisabled();
  expect(screen.getByRole("link", { name: "Body Analysis" })).toHaveAttribute(
    "href",
    "/body-progress",
  );
  expect(screen.getByText("حرکت جایگزین")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "شنا سوئدی" })).toHaveAttribute(
    "href",
    "/exercises/push-up",
  );
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
