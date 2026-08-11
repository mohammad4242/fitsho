import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import * as nutritionApi from "./api";
import { NutritionEstimatePage } from "./NutritionEstimatePage";
import type { NutritionEstimate, WeeklyPlan } from "./types";

vi.mock("./api");
vi.mock("../../shared/AuthenticatedHeader", () => ({ AuthenticatedHeader: () => null }));

const target = (unit: string, values: Partial<{ minimum: number; preferred: number; preferred_maximum: number; maximum: number }> = {}) => ({
  unit, minimum: null, preferred: null, preferred_maximum: null, maximum: null,
  confidence: "high" as const, source_ids: ["who-healthy-diet-2026"],
  explanation_codes: ["SCIENTIFIC_ESTIMATE"], ...values,
});

const estimate: NutritionEstimate = {
  id: "estimate-1", revision: 2, status: "active",
  policy_version: "nutrition-science-v1", formula_version: "mifflin-net-met-v1",
  confidence: "high", confidence_reasons: ["complete_anthropometrics"], is_stale: false,
  created_at: "2026-08-05T12:00:00Z",
  targets: {
    goal_calories: target("kcal/day", { preferred: 2100 }),
    protein: target("g/day", { minimum: 80, preferred: 120 }),
    carbohydrate: target("g/day", { minimum: 236, maximum: 394 }),
    total_fat: target("g/day", { minimum: 35, maximum: 70 }),
    fibre: target("g/day", { minimum: 25, preferred: 29 }),
    free_sugar: target("g/day", { preferred_maximum: 26, maximum: 53 }),
    saturated_fat: target("g/day", { maximum: 23 }),
    trans_fat: target("g/day", { maximum: 2 }),
    sodium: target("mg/day", { maximum: 2000 }),
  },
};

const weeklyPlan: WeeklyPlan = {
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
  start_date: "2026-08-08",
  planner_policy_version: "weekly-planner-v1",
  planner_version: "deterministic-heuristic-v1",
  scientific_policy_version: "nutrition-science-v1",
  formula_version: "mifflin-net-met-v1",
  weekly_cost_irr: 8_200_000,
  weekly_budget_irr: 10_000_000,
  budget_status: "within_budget",
  warning_codes: [],
  explanation_codes: ["PHYSICIAN_REVIEW_REQUIRED"],
  input_snapshot: {},
  price_snapshot: { currency: "IRR" },
  food_data_manifest: { catalogue_version: "test" },
  repair_actions: [],
  nutrients: {
    protein: {
      nutrient_code: "protein",
      unit: "g/day",
      reference_kind: null,
      preferred: 120,
      minimum_or_maximum: 80,
      planned: 112,
      difference_from_preferred: -8,
      difference_from_limit: 32,
      status: "below_preferred_but_acceptable",
      reason_codes: ["DIETARY_REFERENCE_GAP"],
      data_confidence: "high",
      explanation_codes: ["DIETARY_REFERENCE_GAP"],
    },
  },
  days: Array.from({ length: 7 }, (_, index) => ({
    day_index: index,
    plan_date: `2026-08-${String(8 + index).padStart(2, "0")}`,
    nutrient_totals: { energy_kcal: 2100 },
    cost_irr: 1_000_000,
    meals: [{
      id: `meal-${index}`,
      slot_role: "main_meal" as const,
      slot_index: 0,
      target_distribution: { goal_calories: 700 },
      nutrient_totals: { energy_kcal: 700 },
      cost_irr: 300_000,
      is_locked: false,
      foods: [{
        food_id: "food-1",
        slug: "chicken-breast",
        name_fa: "سینه مرغ",
        name_en: "Chicken breast",
        grams: 150,
        cost_irr: 200_000,
        nutrients: { protein_g: 46 },
      }],
    }],
  })),
  created_at: "2026-08-09T12:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
  vi.mocked(nutritionApi.getCurrentNutritionEstimate).mockResolvedValue(estimate);
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(null);
  vi.mocked(nutritionApi.getDailyTracking).mockResolvedValue({
    entry_date: "2026-08-11",
    check_in_status: "not_recorded",
    plan_revision_id: null,
    data_status: "insufficient_data",
    actual_totals: {},
    entries: [],
  });
  vi.mocked(nutritionApi.getShoppingList).mockResolvedValue({ plan_id: "plan-1", plan_revision: 1, approval_status: "pending", warning_codes: ["PLAN_NOT_ACTIVE"], total_cost_irr: 1_400_000, items: [{ food_id: "food-1", slug: "chicken-breast", name_fa: "سینه مرغ", name_en: "Chicken breast", required_quantity: 1050, canonical_unit: "g", cost_irr: 1_400_000 }] });
  vi.mocked(nutritionApi.listWeeklyNutritionPlans).mockResolvedValue([]);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

it("animates the real calorie target and full ring on the same timeline", async () => {
  const frames: FrameRequestCallback[] = [];
  vi.mocked(matchMedia).mockReturnValue({ matches: false } as MediaQueryList);
  vi.stubGlobal("requestAnimationFrame", vi.fn((callback: FrameRequestCallback) => {
    frames.push(callback);
    return frames.length;
  }));
  vi.stubGlobal("cancelAnimationFrame", vi.fn());
  await i18n.changeLanguage("fa");

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  const calorieCard = await screen.findByRole("region", { name: "کالری هدف روزانه" });
  const progress = screen.getByRole("progressbar", { name: "پیشرفت کالری هدف" });
  expect(within(calorieCard).getByText("۰")).toBeInTheDocument();
  expect(progress).toHaveAttribute("aria-valuenow", "0");
  expect(within(progress).getByText("0%")).toBeInTheDocument();

  await waitFor(() => expect(frames).toHaveLength(1));
  act(() => frames.shift()?.(100));
  act(() => frames.shift()?.(1_000));

  expect(within(calorieCard).getByText("۲٬۱۰۰")).toBeInTheDocument();
  expect(progress).toHaveAttribute("aria-valuenow", "2100");
  expect(progress).toHaveAttribute("aria-valuemax", "2100");
  expect(within(progress).getByText("100%")).toBeInTheDocument();
});

it("shows doctor supervision tools without inventing a pending plan", async () => {
  await i18n.changeLanguage("fa");

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  const supervision = (await screen.findByRole("heading", { name: "تحت نظر پزشک" })).closest("section");
  expect(supervision).not.toBeNull();
  expect(within(supervision!).getByRole("link", { name: /مکمل‌های من/ })).toHaveAttribute("href", "/nutrition-supplements");
  expect(within(supervision!).getByRole("link", { name: /آزمایشات من/ })).toHaveAttribute("href", "/nutrition-labs");
  expect(within(supervision!).getByText("تأیید برنامه غذایی")).toBeInTheDocument();
  expect(within(supervision!).getByText("راهنمایی‌های پزشک")).toBeInTheDocument();
  expect(within(supervision!).getByText("پس از ساخت برنامه")).toBeInTheDocument();
  expect(within(supervision!).queryByText("در انتظار تأیید پزشک")).not.toBeInTheDocument();
});

it("keeps the red pending status for a plan awaiting physician approval", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(weeklyPlan);

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  const supervision = (await screen.findByRole("heading", { name: "تحت نظر پزشک" })).closest("section");
  expect(within(supervision!).getByText("در انتظار تأیید پزشک")).toHaveClass("nutrition-doctor-status--pending");
});

it("uses one compact weekly nutrition plan action", async () => {
  await i18n.changeLanguage("fa");

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  expect(await screen.findByRole("button", { name: "ساخت برنامه تغذیه هفتگی" })).toBeInTheDocument();
  expect(screen.queryByText("گام بعد")).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "برنامه هفتگی شخصی‌ات را بساز" })).not.toBeInTheDocument();
  expect(screen.queryByText(/فیتشو هدف‌های علمی/)).not.toBeInTheDocument();
});

it("keeps real tracked context while presenting the calculated calorie goal", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.getDailyTracking).mockResolvedValue({
    entry_date: "2026-08-11",
    check_in_status: "on_plan",
    plan_revision_id: null,
    data_status: "sufficient",
    actual_totals: {
      energy_kcal: 1050,
      protein_g: 61,
      carbohydrate_g: 118,
      total_fat_g: 38,
    },
    entries: [{
      id: "entry-1",
      entry_date: "2026-08-11",
      plan_revision_id: null,
      planned_meal_id: null,
      food_id: null,
      display_name: "ناهار",
      quantity_grams: null,
      source: "manual",
      confidence: "high",
      nutrients: { energy_kcal: 1050 },
      warning_codes: [],
    }],
  });

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  const calorieCard = await screen.findByRole("region", { name: "کالری هدف روزانه" });
  expect(within(calorieCard).getByText("۲٬۱۰۰")).toBeInTheDocument();
  expect(within(calorieCard).getByText("دریافت امروز ۱٬۰۵۰ کیلوکالری")).toBeInTheDocument();
  expect(screen.getByText("۶۱ گرم")).toBeInTheDocument();
  expect(screen.getByRole("progressbar", { name: "پیشرفت کالری هدف" })).toHaveAttribute("aria-valuemax", "2100");
});

it("generates and displays a seven-day draft without claiming physician approval", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.createWeeklyNutritionPlan).mockResolvedValue({
    generation_id: "generation-1",
    outcome: "success",
    reason_codes: ["SAFE_FEASIBLE_DRAFT_GENERATED"],
    warning_codes: [],
    plan: weeklyPlan,
  });
  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  await userEvent.click(await screen.findByRole("button", { name: "ساخت برنامه تغذیه هفتگی" }));

  expect(await screen.findByRole("heading", { name: "برنامه غذایی تو" })).toBeInTheDocument();
  expect(screen.getByText("در انتظار بررسی پزشک")).toBeInTheDocument();
  expect(screen.queryByText("تأییدشده توسط پزشک")).not.toBeInTheDocument();
  expect(screen.getAllByRole("tab")).toHaveLength(7);
  expect(screen.getAllByText("سینه مرغ")).toHaveLength(2);
});

it("shows the scientific calorie and nutrient estimate with its limits in Persian", async () => {
  await i18n.changeLanguage("fa");
  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  expect(await screen.findByRole("heading", { name: "تغذیه" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "کالری هدف روزانه" })).toBeInTheDocument();
  expect(screen.getByText(/۲٬۱۰۰/)).toBeInTheDocument();
  expect(screen.getByText(/۱۲۰/)).toBeInTheDocument();
  expect(screen.getByText("اطمینان بالا")).toBeInTheDocument();
  expect(screen.getByText(/برآورد علمی است، نه تشخیص یا نسخه پزشکی/)).toBeInTheDocument();
  expect(screen.queryByText(/قیمت این هفته/)).not.toBeInTheDocument();
  expect(screen.getByText(/nutrition-science-v1/)).toBeInTheDocument();
  expect(screen.getByText("جزئیات علمی و حدود ایمنی").closest("details")).not.toHaveAttribute("open");
});

it("uses complete English copy and left-to-right layout", async () => {
  await i18n.changeLanguage("en");
  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  const heading = await screen.findByRole("heading", { name: "Nutrition" });
  expect(heading.closest("main")).toHaveAttribute("dir", "ltr");
  expect(screen.getByText("High confidence")).toBeInTheDocument();
  expect(screen.getByText(/scientific estimate, not a diagnosis or medical prescription/i)).toBeInTheDocument();
});

it("supports locking, feedback, and a confirmed revision-safe meal removal", async () => {
  await i18n.changeLanguage("en");
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(weeklyPlan);
  vi.mocked(nutritionApi.setMealLock).mockResolvedValue({ is_locked: true });
  vi.mocked(nutritionApi.saveMealFeedback).mockResolvedValue({});
  vi.mocked(nutritionApi.previewMealRemoval).mockResolvedValue({ expected_plan_revision_id: "plan-1", meal_id: "meal-0", daily_delta: { energy_kcal: -700 }, weekly_cost_delta_irr: -300_000, new_warning_codes: ["MEAL_REMOVAL_MAY_REDUCE_ADEQUACY"] });
  vi.mocked(nutritionApi.confirmMealRemoval).mockResolvedValue({ ...weeklyPlan, id: "plan-2", revision: 2, supersedes_plan_id: "plan-1" });
  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  await userEvent.click(await screen.findByRole("button", { name: "Lock meal" }));
  expect(nutritionApi.setMealLock).toHaveBeenCalledWith("plan-1", "meal-0", true);
  await userEvent.click(screen.getByRole("button", { name: "Unlock" }));
  await userEvent.click(screen.getByRole("button", { name: "Liked" }));
  expect(nutritionApi.saveMealFeedback).toHaveBeenCalledWith("plan-1", "meal-0", "liked");
  await userEvent.click(screen.getByRole("button", { name: "Preview removal" }));
  expect(await screen.findByRole("dialog", { name: "Confirm meal removal" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Create new revision" }));
  expect(nutritionApi.confirmMealRemoval).toHaveBeenCalledWith("plan-1", "meal-0", "plan-1");
  expect(await screen.findByText("Revision 2")).toBeInTheDocument();
});
