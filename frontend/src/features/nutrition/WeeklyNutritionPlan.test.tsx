import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import { ApiError } from "../../shared/apiClient";
import * as nutritionApi from "./api";
import { WeeklyNutritionPlan } from "./WeeklyNutritionPlan";
import type { WeeklyPlan } from "./types";

vi.mock("./api");

const meal = (id: string, name: string, isLocked = false, foods = [food("food-1", "Chicken breast")]) => ({
  id,
  catalogue_meal_id: `catalogue-${id}`,
  catalogue_meal_category: "lunch",
  name_fa: name,
  name_en: name,
  meal_code: id === "meal-0" ? "LU01" : "LU02",
  image_url: id === "meal-1" ? "/media/meal-2.png" : null,
  slot_role: "main_meal" as const,
  slot_index: 0,
  target_distribution: { goal_calories: 700 },
  nutrient_totals: { energy_kcal: id === "meal-1" ? 650 : 700, protein_g: 40 },
  cost_irr: id === "meal-1" ? 250_000 : 300_000,
  is_locked: isLocked,
  foods,
});

const food = (id: string, name: string, grams = 90) => ({
  food_id: id,
  slug: id,
  name_fa: name,
  name_en: name,
  grams,
  cost_irr: 100_000,
  nutrients: { energy_kcal: 150, protein_g: 30 },
});

const plan = (locked = false): WeeklyPlan => ({
  id: "plan-1",
  revision: 1,
  lifecycle_status: "pending_physician_review",
  is_user_visible: true,
  physician_approved: false,
  review_status: "pending",
  physician_approved_at: null,
  physician_display_name: null,
  physician_user_visible_notes: null,
  physician_change_summary: [],
  supersedes_plan_id: null,
  start_date: "2026-09-05",
  planner_policy_version: "policy",
  planner_version: "planner",
  scientific_policy_version: "science",
  formula_version: "formula",
  weekly_cost_irr: 1_000_000,
  weekly_budget_irr: 2_000_000,
  budget_status: "within_budget",
  warning_codes: [],
  explanation_codes: [],
  input_snapshot: {},
  price_snapshot: {},
  food_data_manifest: {},
  repair_actions: [],
  nutrients: {},
  days: Array.from({ length: 7 }, (_, dayIndex) => ({
    day_index: dayIndex,
    plan_date: `2026-09-${String(5 + dayIndex).padStart(2, "0")}`,
    nutrient_totals: { energy_kcal: 700 },
    cost_irr: 100_000,
    meals: [
      meal(dayIndex === 1 ? "meal-1" : "meal-0", dayIndex === 1 ? "Alternative meal" : "Target meal", locked),
    ],
  })),
  created_at: "2026-09-04T12:00:00Z",
});

const mealOption = {
  id: "meal-1",
  name_fa: "Alternative meal",
  name_en: "Alternative meal",
  meal_code: "LU02",
  image_url: "/media/meal-2.png",
  slot_role: "main_meal",
  nutrient_totals: { energy_kcal: 650, protein_g: 40 },
  cost_irr: 250_000,
  is_locked: false,
};

const foodOption = {
  food_id: "food-2",
  slug: "rice",
  name_fa: "Rice",
  name_en: "Rice",
  image_url: "/media/rice.png",
  grams: 90,
  cost_irr: 50_000,
  nutrients: { energy_kcal: 120, protein_g: 3 },
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(nutritionApi.getShoppingList).mockResolvedValue({
    plan_id: "plan-1", plan_revision: 1, approval_status: "pending", warning_codes: [],
    total_cost_irr: 100_000, items: [],
  });
  vi.mocked(nutritionApi.listWeeklyNutritionPlans).mockResolvedValue([]);
  vi.mocked(nutritionApi.getMealFeedback).mockResolvedValue({ feedback: {} });
  vi.mocked(nutritionApi.saveMealFeedback).mockResolvedValue({
    meal_id: "meal-0", feedback_type: "liked", change_kind: "plan_control_metadata",
  });
  vi.mocked(nutritionApi.setMealLock).mockResolvedValue({ is_locked: false });
  vi.mocked(nutritionApi.getMealReplacementOptions).mockResolvedValue({ target_meal_id: "meal-0", options: [mealOption] });
  vi.mocked(nutritionApi.getFoodReplacementOptions).mockResolvedValue({ target_meal_id: "meal-0", target_food_id: "food-1", options: [foodOption] });
  vi.mocked(nutritionApi.previewMealRemoval).mockResolvedValue({
    expected_plan_revision_id: "plan-1", meal_id: "meal-0", daily_delta: { energy_kcal: -700, protein_g: -40 },
    weekly_cost_delta_irr: -300_000, new_warning_codes: ["MEAL_REMOVAL_MAY_REDUCE_ADEQUACY"],
  });
  vi.mocked(nutritionApi.previewMealReplacement).mockResolvedValue({
    expected_plan_revision_id: "plan-1", meal_id: "meal-0", replacement_meal_id: "meal-1",
    daily_delta: { energy_kcal: -50, protein_g: 0 }, weekly_cost_delta_irr: -50_000,
  });
  vi.mocked(nutritionApi.previewFoodReplacement).mockResolvedValue({
    expected_plan_revision_id: "plan-1", meal_id: "meal-0", food_id: "food-1", replacement_food_id: "food-2",
    meal_delta: { energy_kcal: -30, protein_g: -27 }, cost_delta_irr: -50_000,
  });
  vi.mocked(nutritionApi.confirmMealRemoval).mockResolvedValue({ ...plan(), id: "plan-2", revision: 2 });
  vi.mocked(nutritionApi.confirmMealReplacement).mockResolvedValue({ ...plan(), id: "plan-2", revision: 2 });
  vi.mocked(nutritionApi.confirmFoodReplacement).mockResolvedValue({ ...plan(), id: "plan-2", revision: 2 });
});

async function openMeal(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.queryByText("Nutrition plan") ?? screen.getByText("برنامه تغذیه"));
  await user.click(screen.getByText("LU01 — Target meal").closest("summary")!);
}

it("awaits feedback, marks the persisted choice, and switches feedback values", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><WeeklyNutritionPlan language="en" plan={plan()} /></MemoryRouter>);
  await openMeal(user);

  await user.click(screen.getByRole("button", { name: "Liked" }));
  await waitFor(() => expect(nutritionApi.saveMealFeedback).toHaveBeenCalledWith("plan-1", "meal-0", "liked"));
  expect(screen.getByRole("button", { name: /Liked/ })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: /Liked/ })).toHaveTextContent("✓");

  vi.mocked(nutritionApi.saveMealFeedback).mockResolvedValueOnce({
    meal_id: "meal-0", feedback_type: "disliked", change_kind: "plan_control_metadata",
  });
  await user.click(screen.getByRole("button", { name: "Suggest less often" }));
  await waitFor(() => expect(nutritionApi.saveMealFeedback).toHaveBeenLastCalledWith("plan-1", "meal-0", "disliked"));
  expect(screen.getByRole("button", { name: /Suggest less often/ })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: /Liked/ })).toHaveAttribute("aria-pressed", "false");
});

it("restores persisted feedback when the plan data is loaded again", async () => {
  vi.mocked(nutritionApi.getMealFeedback).mockResolvedValue({ feedback: { "meal-0": "disliked" } });
  const user = userEvent.setup();
  const rendered = render(<MemoryRouter><WeeklyNutritionPlan language="en" plan={plan()} /></MemoryRouter>);
  await openMeal(user);
  expect(screen.getByRole("button", { name: /Suggest less often/ })).toHaveAttribute("aria-pressed", "true");
  rendered.unmount();
  render(<MemoryRouter><WeeklyNutritionPlan language="en" plan={plan()} /></MemoryRouter>);
  await openMeal(user);
  expect(screen.getByRole("button", { name: /Suggest less often/ })).toHaveAttribute("aria-pressed", "true");
});

it("shows a localized domain error when feedback cannot be saved", async () => {
  vi.mocked(nutritionApi.saveMealFeedback).mockRejectedValueOnce(
    new ApiError(409, "review in progress", null, "PLAN_REVIEW_IN_PROGRESS"),
  );
  const user = userEvent.setup();
  render(<MemoryRouter><WeeklyNutritionPlan language="fa" plan={plan()} /></MemoryRouter>);
  await openMeal(user);
  await user.click(screen.getByRole("button", { name: "پسندیدم" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("این نسخه در حال بررسی پزشک است");
});

it("opens a visible removal dialog and replaces the current plan after confirmation", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><WeeklyNutritionPlan language="en" plan={plan()} /></MemoryRouter>);
  await openMeal(user);
  await user.click(screen.getByRole("button", { name: "Remove meal" }));

  const dialog = await screen.findByRole("dialog", { name: "Preview meal removal" });
  expect(within(dialog).getByText(/LU01 — Target meal/)).toBeInTheDocument();
  expect(within(dialog).getByText(/Confirming creates a new revision/)).toBeInTheDocument();
  expect(within(dialog).getByText(/physician review/i)).toBeInTheDocument();
  await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("dialog", { name: "Preview meal removal" })).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Remove meal" }));
  await user.click(await screen.findByRole("button", { name: "Create new revision" }));
  await waitFor(() => expect(nutritionApi.confirmMealRemoval).toHaveBeenCalledWith("plan-1", "meal-0", "plan-1"));
  expect(await screen.findByText("Revision 2")).toBeInTheDocument();
});

it("requires an explicit meal candidate before preview and confirmation", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><WeeklyNutritionPlan language="en" plan={plan()} /></MemoryRouter>);
  await openMeal(user);
  await user.click(screen.getByRole("button", { name: "Replace meal" }));

  const selector = await screen.findByRole("dialog", { name: "Choose a replacement meal" });
  expect(nutritionApi.previewMealReplacement).not.toHaveBeenCalled();
  await user.click(within(selector).getByRole("button", { name: /Alternative meal/ }));
  await user.click(within(selector).getByRole("button", { name: "Preview meal replacement" }));
  await waitFor(() => expect(nutritionApi.previewMealReplacement).toHaveBeenCalledWith("plan-1", "meal-0", "meal-1"));
  await user.click(await screen.findByRole("button", { name: "Create new revision" }));
  expect(nutritionApi.confirmMealReplacement).toHaveBeenCalledWith("plan-1", "meal-0", "meal-1");
});

it("requires an explicit ingredient and food candidate before preview", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><WeeklyNutritionPlan language="en" plan={plan()} /></MemoryRouter>);
  await openMeal(user);
  await user.click(screen.getByRole("button", { name: "Replace ingredient" }));

  const selector = await screen.findByRole("dialog", { name: "Choose an ingredient to replace" });
  await user.click(within(selector).getByRole("button", { name: /Chicken breast/ }));
  expect(nutritionApi.previewFoodReplacement).not.toHaveBeenCalled();
  await user.click(within(selector).getByRole("button", { name: /Rice/ }));
  await user.click(within(selector).getByRole("button", { name: "Preview ingredient replacement" }));
  await waitFor(() => expect(nutritionApi.previewFoodReplacement).toHaveBeenCalledWith("plan-1", "meal-0", "food-1", "food-2"));
});

it("disables plan-defining controls for locked meals and restores them after unlock", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><WeeklyNutritionPlan language="en" plan={plan(true)} /></MemoryRouter>);
  await openMeal(user);
  expect(screen.getByRole("button", { name: "Remove meal" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Replace meal" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Replace ingredient" })).toBeDisabled();

  vi.mocked(nutritionApi.setMealLock).mockResolvedValueOnce({ is_locked: false });
  await user.click(screen.getByRole("button", { name: "Unlock" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Remove meal" })).not.toBeDisabled());
});
