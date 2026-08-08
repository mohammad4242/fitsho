import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

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
  vi.mocked(nutritionApi.getCurrentNutritionEstimate).mockResolvedValue(estimate);
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(null);
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

  await userEvent.click(await screen.findByRole("button", { name: "ساخت برنامه هفتگی" }));

  expect(await screen.findByRole("heading", { name: "برنامه غذایی تو" })).toBeInTheDocument();
  expect(screen.getByText("در انتظار بررسی پزشک")).toBeInTheDocument();
  expect(screen.queryByText("تأییدشده توسط پزشک")).not.toBeInTheDocument();
  expect(screen.getAllByRole("tab")).toHaveLength(7);
  expect(screen.getByText("سینه مرغ")).toBeInTheDocument();
});

it("shows the scientific calorie and nutrient estimate with its limits in Persian", async () => {
  await i18n.changeLanguage("fa");
  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  expect(await screen.findByRole("heading", { name: "هدف روزانه تغذیه" })).toBeInTheDocument();
  expect(screen.getByText(/۲٬۱۰۰/)).toBeInTheDocument();
  expect(screen.getByText(/۱۲۰/)).toBeInTheDocument();
  expect(screen.getByText("اطمینان بالا")).toBeInTheDocument();
  expect(screen.getByText(/برآورد علمی است، نه تشخیص یا نسخه پزشکی/)).toBeInTheDocument();
  expect(screen.getByText(/nutrition-science-v1/)).toBeInTheDocument();
});

it("uses complete English copy and left-to-right layout", async () => {
  await i18n.changeLanguage("en");
  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  const heading = await screen.findByRole("heading", { name: "Daily nutrition targets" });
  expect(heading.closest("main")).toHaveAttribute("dir", "ltr");
  expect(screen.getByText("High confidence")).toBeInTheDocument();
  expect(screen.getByText(/scientific estimate, not a diagnosis or medical prescription/i)).toBeInTheDocument();
});
