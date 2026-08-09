import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import { ApiError } from "../../shared/apiClient";
import type { WorkoutPlan } from "./types";

const api = vi.hoisted(() => ({
  getActiveWorkoutPlan: vi.fn(),
  getWorkoutPlanHistory: vi.fn(),
  getWorkoutPlan: vi.fn(),
  generateWorkoutPlan: vi.fn(),
}));

vi.mock("./api", () => api);
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
                body_region: "upper_body",
                primary_muscle: "chest",
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
            body_region: "upper_body",
            primary_muscle: "chest",
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

beforeEach(() => {
  api.getActiveWorkoutPlan.mockReset();
  api.getWorkoutPlanHistory.mockReset();
  api.getWorkoutPlan.mockReset();
  api.generateWorkoutPlan.mockReset();
  api.getWorkoutPlanHistory.mockResolvedValue([]);
  api.generateWorkoutPlan.mockResolvedValue({ plan, reused: false });
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

  expect(await screen.findByText("در انتظار تأیید مربی")).toBeInTheDocument();
  expect(screen.getByText("پرس سینه دمبل")).toBeInTheDocument();
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
      created_at: approvedPlan.created_at,
      activated_at: approvedPlan.activated_at,
      is_active: true,
      coach_review: approvedPlan.coach_review,
    },
    {
      id: plan.id,
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

  expect(await screen.findByText("تأییدشده توسط مربی سارا")).toBeInTheDocument();
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

it("uses the supplied plan video behind the workout page", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(null);

  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  expect(await screen.findByTestId("member-header-video")).toHaveAttribute(
    "poster",
    expect.stringContaining("plan-focus-fallback"),
  );
  expect(screen.getByTestId("member-header-video").parentElement).toHaveClass(
    "member-page-background",
  );
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
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={6} /></MemoryRouter>);

  expect(await screen.findByLabelText("دوره 6 هفته‌ای")).toBeInTheDocument();
  expect(screen.getByText("پرس سینه دمبل")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "نمایش حرکت پرس سینه دمبل" })).toHaveAttribute(
    "src",
    "/media/bench.gif",
  );
  expect(screen.getByRole("link", { name: "مشاهده جزئیات حرکت" })).toHaveAttribute(
    "href",
    "/exercises/dumbbell-bench-press",
  );
  expect(screen.getByRole("button", { name: "دانلود PDF" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "بازخورد پایان دوره" })).toBeDisabled();
  expect(screen.getByRole("link", { name: "مشاهده پیشرفت بدنی" })).toHaveAttribute(
    "href",
    "/body-progress",
  );
  expect(screen.getByText("حرکت جایگزین")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "شنا سوئدی" })).toHaveAttribute(
    "href",
    "/exercises/push-up",
  );
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
