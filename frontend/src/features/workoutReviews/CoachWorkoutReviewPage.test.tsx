import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import type { WorkoutReviewDetail, WorkoutReviewQueueItem } from "./types";

const api = vi.hoisted(() => ({
  listWorkoutReviews: vi.fn(),
  getWorkoutReview: vi.fn(),
  claimWorkoutReview: vi.fn(),
  renewWorkoutReview: vi.fn(),
  saveWorkoutReviewDraft: vi.fn(),
  approveWorkoutReview: vi.fn(),
}));

vi.mock("./api", () => api);
vi.mock("../../shared/AuthenticatedHeader", () => ({
  AuthenticatedHeader: () => <header>Fitsho</header>,
}));

import { CoachWorkoutReviewPage } from "./CoachWorkoutReviewPage";

const queueItem: WorkoutReviewQueueItem = {
  id: "review-1",
  source_plan_id: "plan-1",
  user_id: "member-1",
  member_display_name: "محمد",
  fitness_goal: "build_muscle",
  experience_level: "beginner",
  status: "pending",
  claimed_by_user_id: null,
  lease_expires_at: null,
  draft_revision: 1,
  created_at: "2026-08-09T08:00:00Z",
  approved_at: null,
};

const detail: WorkoutReviewDetail = {
  ...queueItem,
  status: "claimed",
  claimed_by_user_id: "coach-1",
  lease_expires_at: "2026-08-09T10:00:00Z",
  coach_note: null,
  draft: {
    days: [
      {
        day_number: 1,
        exercises: [
          {
            order_index: 1,
            exercise_id: "exercise-1",
            sets: 3,
            reps_min: 8,
            reps_max: 12,
            rest_seconds: 90,
            notes_en: null,
            notes_fa: null,
          },
        ],
      },
    ],
  },
  source_plan: {
    id: "plan-1",
    status: "active",
    created_at: "2026-08-09T08:00:00Z",
    activated_at: "2026-08-09T08:00:00Z",
    plan_duration_weeks: 4,
    is_stale: false,
    days: [
      {
        day_number: 1,
        title_en: "Upper body",
        title_fa: "بالاتنه",
        estimated_duration_minutes: 45,
        exercises: [
          {
            id: "workout-plan-exercise-1",
            order_index: 1,
            sets: 3,
            reps_min: 8,
            reps_max: 12,
            rest_seconds: 90,
            rir: 2,
            estimated_minutes: 5,
            notes_en: null,
            notes_fa: null,
            alternatives: [],
            exercise: {
              id: "exercise-1",
              slug: "bench-press",
              name_en: "Bench Press",
              name_fa: "پرس سینه",
              content_type: "exercise",
              body_region: "upper_body",
              primary_muscle: "chest",
              muscle_focus: "mid_chest",
              labels: [],
              secondary_muscles: [],
              equipment: [],
              difficulty: "beginner",
              media_path: "/placeholder.svg",
              media_type: "placeholder",
            },
          },
        ],
      },
    ],
    coach_review: {
      state: "pending_coach_review",
      coach_display_name: null,
      coach_note: null,
      approved_at: null,
    },
  },
  exercise_options: [
    { id: "exercise-1", name_en: "Bench Press", name_fa: "پرس سینه" },
    { id: "exercise-2", name_en: "Push-Up", name_fa: "شنا سوئدی" },
  ],
};

beforeEach(() => {
  Object.values(api).forEach((mock) => mock.mockReset());
  api.listWorkoutReviews.mockResolvedValue([queueItem]);
  api.claimWorkoutReview.mockResolvedValue(detail);
  api.getWorkoutReview.mockResolvedValue(detail);
  api.renewWorkoutReview.mockResolvedValue(detail);
  api.saveWorkoutReviewDraft.mockResolvedValue({ ...detail, draft_revision: 2 });
  api.approveWorkoutReview.mockResolvedValue({ ...detail, status: "approved" });
});

function renderPage() {
  return render(
    <MemoryRouter>
      <CoachWorkoutReviewPage />
    </MemoryRouter>,
  );
}

it("shows the three review queues and claims a pending plan", async () => {
  const user = userEvent.setup();
  renderPage();

  expect(await screen.findByRole("tab", { name: "در انتظار بررسی" })).toBeVisible();
  expect(screen.getByRole("tab", { name: "در حال بررسی من" })).toBeVisible();
  expect(screen.getByRole("tab", { name: "تأییدشده" })).toBeVisible();

  await user.click(await screen.findByRole("button", { name: "شروع بازبینی" }));

  expect(api.claimWorkoutReview).toHaveBeenCalledWith("review-1");
  expect(await screen.findByLabelText("تعداد ست روز ۱ حرکت ۱")).toBeEnabled();
});

it("saves permitted edits with the current revision", async () => {
  const user = userEvent.setup();
  renderPage();
  await user.click(await screen.findByRole("button", { name: "شروع بازبینی" }));
  const sets = await screen.findByLabelText("تعداد ست روز ۱ حرکت ۱");
  await user.clear(sets);
  await user.type(sets, "4");
  await user.type(screen.getByLabelText("یادداشت مربی برای کاربر"), "فرم را کنترل کن");

  await user.click(screen.getByRole("button", { name: "ذخیره پیش‌نویس" }));

  expect(api.saveWorkoutReviewDraft).toHaveBeenCalledWith(
    "review-1",
    expect.objectContaining({
      expected_revision: 1,
      coach_note: "فرم را کنترل کن",
      days: expect.arrayContaining([
        expect.objectContaining({
          exercises: expect.arrayContaining([expect.objectContaining({ sets: 4 })]),
        }),
      ]),
    }),
  );
});

it("approves the saved coach version and refreshes the approved queue", async () => {
  const user = userEvent.setup();
  renderPage();
  await user.click(await screen.findByRole("button", { name: "شروع بازبینی" }));

  await user.click(screen.getByRole("button", { name: "تأیید و ارسال برای کاربر" }));

  expect(api.approveWorkoutReview).toHaveBeenCalledWith("review-1", 1);
  expect(api.listWorkoutReviews).toHaveBeenLastCalledWith("approved");
});
