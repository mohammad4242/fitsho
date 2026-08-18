import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import { ApiError } from "../../shared/apiClient";
import type { WorkoutPlan, WorkoutCycleWeeklyCheckIn } from "./types";

const api = vi.hoisted(() => ({
  getCurrentWorkoutCycle: vi.fn(),
  getCurrentWeeklyCheckIn: vi.fn(),
  saveCurrentWeeklyCheckIn: vi.fn(),
}));

vi.mock("./api", () => api);

import { WeeklyCheckInCard } from "./WeeklyCheckInCard";

const firstExercise = {
  id: "wpe-1",
  order_index: 1,
  sets: 3,
  reps_min: 8,
  reps_max: 12,
  rest_seconds: 90,
  rir: 2,
  estimated_minutes: 8,
  notes_en: null,
  notes_fa: null,
  alternatives: [],
  exercise: {
    id: "exercise-1",
    slug: "squat",
    name_en: "Squat",
    name_fa: "اسکوات",
    content_type: "exercise" as const,
    body_region: "lower_body" as const,
    primary_muscle: "quadriceps" as const,
    muscle_focus: "general_quadriceps" as const,
    labels: [],
    secondary_muscles: [],
    equipment: ["bodyweight" as const],
    difficulty: "beginner" as const,
    media_path: "/media/squat.gif",
    media_type: "gif" as const,
  },
};

const secondExercise = {
  ...firstExercise,
  id: "wpe-2",
  order_index: 2,
  exercise: { ...firstExercise.exercise, id: "exercise-2", name_en: "Push-Up", name_fa: "شنا" },
};

const plan: WorkoutPlan = {
  id: "plan-1",
  status: "active",
  created_at: "2026-08-01T10:00:00Z",
  activated_at: "2026-08-01T10:00:00Z",
  plan_duration_weeks: 4,
  is_stale: false,
  days: [
    { day_number: 1, title_en: "Day one", title_fa: "روز اول", estimated_duration_minutes: 40, exercises: [firstExercise] },
    { day_number: 2, title_en: "Day two", title_fa: "روز دوم", estimated_duration_minutes: 40, exercises: [secondExercise] },
  ],
};

const savedCheckIn: WorkoutCycleWeeklyCheckIn = {
  id: "check-in-1",
  user_id: "user-1",
  cycle_id: "cycle-1",
  week_number: 2,
  sessions_completed: 1,
  perceived_difficulty: "hard",
  recovery_rating: "average",
  has_pain_or_limitation: true,
  pain_follow_up: { id: "pain-1", workout_plan_exercise_id: "wpe-1", note_optional: "زانو", created_at: "2026-08-08T10:00:00Z" },
  note_optional: null,
  submitted_at: "2026-08-08T10:00:00Z",
  created_at: "2026-08-08T10:00:00Z",
  updated_at: "2026-08-08T10:00:00Z",
};

beforeEach(() => {
  api.getCurrentWorkoutCycle.mockReset();
  api.getCurrentWeeklyCheckIn.mockReset();
  api.saveCurrentWeeklyCheckIn.mockReset();
  api.getCurrentWorkoutCycle.mockResolvedValue({
    cycle_id: "cycle-1",
    workout_plan_id: plan.id,
    started_at: "2026-08-01T10:00:00Z",
    duration_weeks: 4,
    status: "active",
    current_week: 2,
  });
  api.getCurrentWeeklyCheckIn.mockResolvedValue(null);
  api.saveCurrentWeeklyCheckIn.mockResolvedValue({ ...savedCheckIn, week_number: 1, has_pain_or_limitation: false, pain_follow_up: null });
});

afterEach(() => {
  vi.restoreAllMocks();
  void i18n.changeLanguage("fa");
});

it("shows the compact form and one session choice for every value from zero", async () => {
  render(<WeeklyCheckInCard plan={plan} />);

  expect(await screen.findByRole("heading", { name: "چک‌این هفتگی" })).toBeInTheDocument();
  expect(screen.getByText("هفته ۲")).toBeInTheDocument();
  expect(screen.getByRole("radio", { name: "۰" })).toBeInTheDocument();
  expect(screen.getByRole("radio", { name: "۱" })).toBeInTheDocument();
  expect(screen.getByRole("radio", { name: "۲" })).toBeInTheDocument();
  expect(screen.queryByRole("radio", { name: "۳" })).not.toBeInTheDocument();
});

it("supports difficulty and recovery selections", async () => {
  const user = userEvent.setup();
  render(<WeeklyCheckInCard plan={plan} />);

  await screen.findByRole("heading", { name: "چک‌این هفتگی" });
  await user.click(screen.getByRole("radio", { name: "خیلی سنگین" }));
  await user.click(screen.getByRole("radio", { name: "ضعیف" }));

  expect(screen.getByRole("radio", { name: "خیلی سنگین" })).toBeChecked();
  expect(screen.getByRole("radio", { name: "ضعیف" })).toBeChecked();
});

it("only shows prescribed pain follow-up after pain is selected", async () => {
  const user = userEvent.setup();
  render(<WeeklyCheckInCard plan={plan} />);

  await screen.findByRole("heading", { name: "چک‌این هفتگی" });
  expect(screen.queryByRole("combobox", { name: "حرکت آسیب‌دیده" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("radio", { name: "بله" }));

  expect(screen.getByRole("combobox", { name: "حرکت آسیب‌دیده" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "اسکوات" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "شنا" })).toBeInTheDocument();
  expect(screen.getByLabelText("توضیح کوتاه (اختیاری)")).toBeInTheDocument();
});

it("submits the current form and shows the completed state", async () => {
  const user = userEvent.setup();
  render(<WeeklyCheckInCard plan={plan} />);

  await screen.findByRole("heading", { name: "چک‌این هفتگی" });
  await user.click(screen.getByRole("radio", { name: "۲" }));
  await user.click(screen.getByRole("radio", { name: "مناسب" }));
  await user.click(screen.getByRole("radio", { name: "خوب" }));
  await user.click(screen.getByRole("button", { name: "ثبت چک‌این" }));

  await waitFor(() => expect(api.saveCurrentWeeklyCheckIn).toHaveBeenCalledWith({
    sessions_completed: 2,
    perceived_difficulty: "appropriate",
    recovery_rating: "good",
    has_pain_or_limitation: false,
    pain_follow_up: null,
    note_optional: null,
  }));
  expect(await screen.findByText("چک‌این این هفته ثبت شد")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "ویرایش چک‌این" })).toBeInTheDocument();
});

it("loads an existing check-in as completed and allows editing it", async () => {
  api.getCurrentWeeklyCheckIn.mockResolvedValue(savedCheckIn);
  const user = userEvent.setup();
  render(<WeeklyCheckInCard plan={plan} />);

  expect(await screen.findByText("چک‌این این هفته ثبت شد")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "ویرایش چک‌این" }));
  expect(screen.getByRole("radio", { name: "سنگین" })).toBeChecked();
  expect(screen.getByRole("combobox", { name: "حرکت آسیب‌دیده" })).toHaveValue("wpe-1");

  await user.click(screen.getByRole("radio", { name: "۰" }));
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));
  await waitFor(() => expect(api.saveCurrentWeeklyCheckIn).toHaveBeenCalled());
});

it("shows loading and API error states cleanly", async () => {
  let resolve: ((value: null) => void) | undefined;
  api.getCurrentWeeklyCheckIn.mockReturnValue(new Promise((r) => { resolve = r; }));
  render(<WeeklyCheckInCard plan={plan} />);
  expect(screen.getByRole("status")).toHaveTextContent("در حال دریافت چک‌این هفتگی…");
  resolve?.(null);
  expect(await screen.findByRole("heading", { name: "چک‌این هفتگی" })).toBeInTheDocument();

  api.saveCurrentWeeklyCheckIn.mockRejectedValue(new ApiError(422, "Invalid check-in"));
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "ثبت چک‌این" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("ثبت چک‌این انجام نشد");
});
