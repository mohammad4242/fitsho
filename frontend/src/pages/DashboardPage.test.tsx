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
  getCurrentNutritionEstimate: vi.fn(),
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
  nutritionApi.getCurrentNutritionEstimate.mockReset();
  nutritionApi.getLatestWeeklyNutritionPlan.mockResolvedValue(null);
  nutritionApi.getDailyTracking.mockRejectedValue(new Error("not tracked"));
  nutritionApi.getCurrentNutritionEstimate.mockResolvedValue(null);
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

it("uses the next workout's first real exercise media in the hero", async () => {
  workoutApi.getActiveWorkoutPlan.mockResolvedValue({
    id: "plan-1",
    days: [{
      day_number: 1,
      title_fa: "فشار بالاتنه",
      title_en: "Upper push",
      estimated_duration_minutes: 52,
      exercises: [{
        order_index: 1,
        exercise: {
          id: "exercise-1",
          slug: "bench-press",
          name_fa: "پرس سینه",
          name_en: "Bench press",
          media_path: "/media/bench.webp",
          media_type: "image",
        },
      }],
    }],
  });

  render(<MemoryRouter><DashboardPage /></MemoryRouter>);

  expect(await screen.findByRole("img", { name: "نمایش حرکت پرس سینه" })).toHaveAttribute(
    "src",
    "/media/bench.webp",
  );
});

it("uses the current scientific estimate when no weekly plan exists", async () => {
  profile.productMode = "both";
  workoutApi.getActiveWorkoutPlan.mockResolvedValue(null);
  nutritionApi.getCurrentNutritionEstimate.mockResolvedValue({
    confidence: "high",
    targets: {
      goal_calories: { preferred: 2200 },
      protein: { preferred: 130 },
      carbohydrate: { preferred: 280 },
      total_fat: { preferred: 68 },
    },
  });
  nutritionApi.getDailyTracking.mockResolvedValue({
    data_status: "sufficient",
    actual_totals: { energy_kcal: 1100, protein_g: 65, carbohydrate_g: 140, total_fat_g: 34 },
    entries: [{}],
  });

  render(<MemoryRouter><DashboardPage /></MemoryRouter>);

  expect(await screen.findByText("۱٬۱۰۰")).toBeInTheDocument();
  expect(screen.getByText("از ۲٬۲۰۰ kcal")).toBeInTheDocument();
  expect(screen.getByRole("progressbar", { name: "پیشرفت کالری امروز" })).toHaveAttribute(
    "aria-valuemax",
    "2200",
  );
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
  expect(screen.getByRole("link", { name: "body analys" })).toHaveAttribute(
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

it("keeps workout, nutrition, and quick actions in the required priority", async () => {
  profile.productMode = "both";
  workoutApi.getActiveWorkoutPlan.mockResolvedValue({
    id: "plan-1",
    days: [{ day_number: 1, title_fa: "فشار بالاتنه", title_en: "Upper push", estimated_duration_minutes: 52, exercises: [] }],
  });
  nutritionApi.getCurrentNutritionEstimate.mockResolvedValue({
    confidence: "high",
    targets: {
      goal_calories: { preferred: 2200 },
      protein: { preferred: 130 },
      carbohydrate: { preferred: 280 },
      total_fat: { preferred: 68 },
    },
  });

  render(<MemoryRouter><DashboardPage /></MemoryRouter>);

  const workout = await screen.findByRole("region", { name: "تمرین امروز" });
  const nutrition = await screen.findByRole("link", { name: "هدف روزانه تغذیه" });
  const quickActions = screen.getByRole("navigation", { name: "دسترسی سریع" });

  expect(workout.compareDocumentPosition(nutrition) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(nutrition.compareDocumentPosition(quickActions) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

it("shows calorie progress against the real target before food is tracked", async () => {
  profile.productMode = "both";
  workoutApi.getActiveWorkoutPlan.mockResolvedValue(null);
  nutritionApi.getCurrentNutritionEstimate.mockResolvedValue({
    confidence: "high",
    targets: {
      goal_calories: { preferred: 2200 },
      protein: { preferred: 130 },
      carbohydrate: { preferred: 280 },
      total_fat: { preferred: 68 },
    },
  });

  render(<MemoryRouter><DashboardPage /></MemoryRouter>);

  expect(await screen.findByRole("progressbar", { name: "پیشرفت کالری امروز" })).toHaveAttribute(
    "aria-valuenow",
    "0",
  );
});

it("routes the minimal body and food analysis shortcuts to their real flows", async () => {
  profile.productMode = "both";
  workoutApi.getActiveWorkoutPlan.mockResolvedValue(null);

  render(<MemoryRouter><DashboardPage /></MemoryRouter>);

  const body = await screen.findByRole("link", { name: "body analys" });
  const food = screen.getByRole("link", { name: "food analys" });

  expect(body).toHaveAttribute("href", "/body-progress");
  expect(food).toHaveAttribute("href", "/nutrition-tracking");
  expect(body.textContent).toBe("body analys");
  expect(food.textContent).toBe("food analys");
  expect(body.querySelector("img")).not.toBeNull();
  expect(food.querySelector("img")).not.toBeNull();
});
