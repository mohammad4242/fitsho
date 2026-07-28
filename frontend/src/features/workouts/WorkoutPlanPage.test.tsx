import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import type { WorkoutPlan } from "./types";

const api = vi.hoisted(() => ({
  getActiveWorkoutPlan: vi.fn(),
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
          exercise: {
            id: "018f0000-0000-7000-8000-000000000002",
            slug: "dumbbell-bench-press",
            name_en: "Dumbbell Bench Press",
            name_fa: "پرس سینه دمبل",
            body_region: "upper_body",
            primary_muscle: "chest",
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
  api.generateWorkoutPlan.mockReset();
  api.generateWorkoutPlan.mockResolvedValue({ plan, reused: false });
});

it("shows the fixed start guide and a generate action when no plan exists", async () => {
  api.getActiveWorkoutPlan.mockResolvedValue(null);
  const user = userEvent.setup();
  render(<MemoryRouter><WorkoutPlanPage planDurationWeeks={4} /></MemoryRouter>);

  expect(await screen.findByRole("heading", { name: "برنامه تمرینی من" })).toBeInTheDocument();
  expect(screen.getByText("قبل از شروع")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "ساخت برنامه" }));

  expect(api.generateWorkoutPlan).toHaveBeenCalledOnce();
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
