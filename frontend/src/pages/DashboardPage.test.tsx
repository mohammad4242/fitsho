import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({
  user: {
    id: "1",
    email: "member@example.com",
    created_at: "2026-07-24T00:00:00Z",
    is_admin: false,
  },
}));
const profile = vi.hoisted(() => ({
  profile: { display_name: "محمد", plan_duration_weeks: 4 },
  productMode: "training" as "training" | "nutrition" | "both",
}));
const workoutApi = vi.hoisted(() => ({
  getActiveWorkoutPlan: vi.fn(),
  generateWorkoutPlan: vi.fn(),
}));
const nutritionApi = vi.hoisted(() => ({
  getLatestWeeklyNutritionPlan: vi.fn(),
  getDailyTracking: vi.fn(),
}));

vi.mock("../features/auth/AuthContext", () => ({ useAuth: () => auth }));
vi.mock("../features/profile/ProfileContext", () => ({ useProfile: () => profile }));
vi.mock("../features/workouts/api", () => workoutApi);
vi.mock("../features/nutrition/api", () => nutritionApi);
vi.mock("../shared/AuthenticatedHeader", () => ({ AuthenticatedHeader: () => null }));

import "../i18n";
import { DashboardPage } from "./DashboardPage";

beforeEach(() => {
  workoutApi.getActiveWorkoutPlan.mockReset();
  workoutApi.generateWorkoutPlan.mockReset();
  nutritionApi.getLatestWeeklyNutritionPlan.mockReset();
  nutritionApi.getDailyTracking.mockReset();
  nutritionApi.getLatestWeeklyNutritionPlan.mockResolvedValue(null);
  nutritionApi.getDailyTracking.mockRejectedValue(new Error("not tracked"));
  profile.productMode = "training";
});

it("surfaces the real next session instead of generic workout copy", async () => {
  workoutApi.getActiveWorkoutPlan.mockResolvedValue({
    id: "plan-1",
    days: [{ day_number: 1, title_fa: "فشار بالاتنه", title_en: "Upper push", estimated_duration_minutes: 52, exercises: [] }],
  });

  render(<MemoryRouter><DashboardPage /></MemoryRouter>);

  expect(await screen.findByRole("heading", { name: "فشار بالاتنه" })).toBeInTheDocument();
  expect(screen.getByText("۵۲ دقیقه")).toBeInTheDocument();
});

it("shows connected real nutrition totals for combined members", async () => {
  profile.productMode = "both";
  workoutApi.getActiveWorkoutPlan.mockResolvedValue(null);
  nutritionApi.getLatestWeeklyNutritionPlan.mockResolvedValue({
    physician_approved: true,
    days: [{ plan_date: new Date().toISOString().slice(0, 10), nutrient_totals: { energy_kcal: 2400, protein_g: 160, carbohydrate_g: 250, total_fat_g: 70 }, meals: [] }],
  });
  nutritionApi.getDailyTracking.mockResolvedValue({ actual_totals: { energy_kcal: 1200, protein_g: 80, carbohydrate_g: 125, total_fat_g: 35 } });

  render(<MemoryRouter><DashboardPage /></MemoryRouter>);

  expect(await screen.findByText("۱٬۲۰۰")).toBeInTheDocument();
  expect(screen.getByText("از ۲٬۴۰۰ kcal")).toBeInTheDocument();
  expect(screen.getByText("۸۰g")).toBeInTheDocument();
});

it("shows nutrition targets and skips workout loading for nutrition-only members", async () => {
  profile.productMode = "nutrition";
  render(<MemoryRouter><DashboardPage /></MemoryRouter>);

  expect(await screen.findByRole("link", { name: /هدف روزانه تغذیه/ })).toHaveAttribute(
    "href",
    "/nutrition-estimate",
  );
  expect(workoutApi.getActiveWorkoutPlan).not.toHaveBeenCalled();
  expect(screen.queryByRole("link", { name: "برنامه تمرینی" })).not.toBeInTheDocument();
});

it("starts generating a plan when the member has no active plan", async () => {
  workoutApi.getActiveWorkoutPlan.mockResolvedValue(null);
  workoutApi.generateWorkoutPlan.mockResolvedValue({ plan: {}, reused: false });
  const user = userEvent.setup();

  render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  );

  await user.click(await screen.findByRole("button", { name: "شروع کن" }));

  expect(workoutApi.generateWorkoutPlan).toHaveBeenCalledOnce();
});

it("links the primary CTA to the active workout plan", async () => {
  workoutApi.getActiveWorkoutPlan.mockResolvedValue({ id: "plan-1" });

  render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  );

  expect(await screen.findByRole("link", { name: "شروع کن" })).toHaveAttribute(
    "href",
    "/workout-plan",
  );
});

it("presents a focused command center without cinematic media", async () => {
  workoutApi.getActiveWorkoutPlan.mockResolvedValue(null);

  render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  );

  await screen.findByRole("heading", { name: "سلام، محمد" });
  expect(screen.getByRole("region", { name: "وضعیت امروز" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "تمرین امروز" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "تمرین امروز" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "مشاهده پیشرفت بدنی" })).toHaveAttribute(
    "href",
    "/body-progress",
  );
  expect(document.querySelector("video")).not.toBeInTheDocument();
});

it("shows real profile context in the workout status", async () => {
  workoutApi.getActiveWorkoutPlan.mockResolvedValue(null);

  render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  );

  await screen.findByRole("heading", { name: "سلام، محمد" });
  expect(screen.getByText("دوره ۴ هفته‌ای")).toBeInTheDocument();
});
