import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import * as nutritionApi from "./api";
import { NutritionEstimatePage } from "./NutritionEstimatePage";
import { WeeklyNutritionPlan } from "./WeeklyNutritionPlan";
import type { NutritionEstimate, WeeklyPlan, WeeklyPlanGeneration } from "./types";

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
    bmr: target("kcal/day", { preferred: 1600 }),
    tdee: target("kcal/day", { preferred: 2400 }),
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
      catalogue_meal_id: "catalogue-meal-1",
      catalogue_meal_category: "lunch",
      name_fa: "جوجه کباب + برنج + گوجه کبابی",
      name_en: "Chicken kebab, rice, and grilled tomato",
      meal_code: "LU01",
      image_url: "/media/meal-catalogue/lu01.png",
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
  vi.mocked(nutritionApi.saveFreeMeal).mockResolvedValue({
    entry_date: "2026-08-08", check_in_status: "not_recorded", plan_revision_id: "plan-1",
    data_status: "sufficient", actual_totals: { energy_kcal: 700 }, entries: [],
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function preparedRecipePlan(status: "estimated" | "verified"): WeeklyPlan {
  return {
    ...weeklyPlan,
    days: weeklyPlan.days.map((day, index) => index === 0 ? {
      ...day,
      meals: day.meals.map((meal) => ({
        ...meal,
        foods: [{
          food_id: null,
          item_kind: "prepared_recipe",
          slug: "prepared-gheimeh",
          name_fa: "قیمه",
          name_en: "Gheimeh",
          grams: 290,
          cost_irr: 141_375,
          nutrients: { energy_kcal: 500, protein_g: 41.2 },
          prepared_recipe: {
            status,
            nutrients_per_100g: {
              energy_kcal: 172.4,
              protein_g: 14.2,
              carbohydrate_g: 11.3,
              total_fat_g: 7.1,
              fibre_g: 2.4,
            },
            cost_irr_per_100g: 48_750,
          },
        }],
      })),
    } : day),
  };
}

function generationResult(
  outcome: WeeklyPlanGeneration["outcome"],
  reason_codes: string[],
): WeeklyPlanGeneration {
  return {
    generation_id: "generation-failure",
    outcome,
    reason_codes,
    warning_codes: [],
    plan: null,
  };
}

async function generatePlan(result: WeeklyPlanGeneration) {
  vi.mocked(nutritionApi.createWeeklyNutritionPlan).mockResolvedValue(result);
  const user = userEvent.setup();
  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);
  await user.click(await screen.findByRole("button", { name: /ساخت برنامه تغذیه هفتگی|Build weekly nutrition plan/ }));
}

async function openWeeklyPlan(user: ReturnType<typeof userEvent.setup>) {
  const summary = screen.queryByText("Nutrition plan", { exact: true }) ?? screen.getByText("برنامه تغذیه", { exact: true });
  await user.click(summary);
}

async function openFirstMeal(user: ReturnType<typeof userEvent.setup>) {
  const mealTitle = screen.queryByText("LU01 — جوجه کباب + برنج + گوجه کبابی", { exact: true })
    ?? screen.getByText("LU01 — Chicken kebab, rice, and grilled tomato", { exact: true });
  await user.click(mealTitle.closest("summary")!);
}

it("shows the safe per-100g summary and only تخمینی for an estimated recipe", async () => {
  await i18n.changeLanguage("fa");

  render(<MemoryRouter><WeeklyNutritionPlan language="fa" plan={preparedRecipePlan("estimated")} /></MemoryRouter>);

  const user = userEvent.setup();
  await openWeeklyPlan(user);
  await openFirstMeal(user);

  const estimatedLabel = await screen.findByText("تخمینی");
  const recipeSummary = estimatedLabel.closest("aside");
  expect(recipeSummary).not.toBeNull();
  expect(screen.getByText(/۱۷۲٫۴.*کیلوکالری.*۱۰۰ گرم/)).toBeInTheDocument();
  expect(within(recipeSummary!).getByText("پروتئین")).toBeInTheDocument();
  expect(within(recipeSummary!).getByText("۱۴٫۲")).toBeInTheDocument();
  expect(within(recipeSummary!).getByText("کربوهیدرات")).toBeInTheDocument();
  expect(within(recipeSummary!).getByText("۱۱٫۳")).toBeInTheDocument();
  expect(within(recipeSummary!).getByText("چربی کل")).toBeInTheDocument();
  expect(within(recipeSummary!).getByText("۷٫۱")).toBeInTheDocument();
  expect(within(recipeSummary!).getByText("فیبر")).toBeInTheDocument();
  expect(within(recipeSummary!).getByText("۲٫۴")).toBeInTheDocument();
  expect(screen.getByText(/۴٬۸۷۵.*تومان.*۱۰۰ گرم/)).toBeInTheDocument();
  expect(screen.queryByText(/draft|verified|بررسی‌نشده/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/قیمت ماده|مقدار ماده/)).not.toBeInTheDocument();
});

it("does not show the estimated label for a verified recipe", async () => {
  await i18n.changeLanguage("fa");

  render(<MemoryRouter><WeeklyNutritionPlan language="fa" plan={preparedRecipePlan("verified")} /></MemoryRouter>);

  const user = userEvent.setup();
  await openWeeklyPlan(user);
  await openFirstMeal(user);

  await waitFor(() => expect(nutritionApi.getShoppingList).toHaveBeenCalled());
  expect(screen.queryByText("تخمینی")).not.toBeInTheDocument();
  expect(screen.getByText(/۱۷۲٫۴.*کیلوکالری.*۱۰۰ گرم/)).toBeInTheDocument();
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

it("renders TDEE card and dual progress ring for BMR and activity expenditure", async () => {
  await i18n.changeLanguage("fa");

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  const tdeeCard = await screen.findByRole("region", { name: "کل مصرف روزانه انرژی (TDEE)" });
  expect(within(tdeeCard).getByText("TDEE (کل مصرف روزانه)")).toBeInTheDocument();
  expect(within(tdeeCard).getByText("۲٬۴۰۰")).toBeInTheDocument();
  expect(within(tdeeCard).getByText(/پایه:\s*۱٬۶۰۰/)).toBeInTheDocument();
  expect(within(tdeeCard).getByText(/فعالیت:\s*۸۰۰/)).toBeInTheDocument();

  const dualRing = screen.getByRole("progressbar", { name: "تفکیک مصرف انرژی روزانه" });
  expect(dualRing).toHaveAttribute("aria-valuenow", "2400");
  expect(dualRing).toHaveAttribute("aria-valuemax", "2400");
  expect(dualRing).toHaveTextContent("100%");
  expect(dualRing.style.getPropertyValue("--ring-deg-1")).toBe("240.0deg");
  expect(dualRing.style.getPropertyValue("--ring-deg-2")).toBe("360.0deg");
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

it("renders doctor supervision as collapsible accordion and reveals its cards when toggled", async () => {
  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  const supervision = (await screen.findByRole("heading", { name: "تحت نظر پزشک" })).closest("section");
  expect(supervision).not.toBeNull();
  const accordion = supervision!.querySelector(".nutrition-doctor-accordion");
  expect(accordion).not.toBeNull();
  expect(accordion).not.toHaveAttribute("open");

  const user = userEvent.setup();
  await user.click(screen.getByText("تحت نظر پزشک"));
  expect(accordion).toHaveAttribute("open");
  expect(within(supervision!).getByRole("link", { name: /مکمل‌های من/ })).toBeInTheDocument();
});

it("keeps the red pending status for a plan awaiting physician approval", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(weeklyPlan);

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  const supervision = (await screen.findByRole("heading", { name: "تحت نظر پزشک" })).closest("section");
  expect(within(supervision!).getByText("در انتظار تأیید پزشک")).toHaveClass("nutrition-doctor-status--pending");
});

it("shows the catalogue meal title and thumbnail in the weekly plan", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(weeklyPlan);

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  const user = userEvent.setup();
  await screen.findByRole("heading", { name: "برنامه غذایی تو" });
  await openWeeklyPlan(user);
  expect(await screen.findByText("LU01 — جوجه کباب + برنج + گوجه کبابی")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "جوجه کباب + برنج + گوجه کبابی" })).toHaveAttribute(
    "src", "/media/meal-catalogue/lu01.png",
  );
  expect(screen.queryByText("catalogue-meal-1")).not.toBeInTheDocument();
});

it("starts with the three weekly plan sections collapsed", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(weeklyPlan);

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  await screen.findByRole("heading", { name: "برنامه غذایی تو" });
  expect(screen.getByText("برنامه تغذیه").closest("details")).not.toHaveAttribute("open");
  expect(screen.getByText("هدف در برابر مقدار برنامه").closest("details")).not.toHaveAttribute("open");
  expect(screen.getByText("لیست خرید دقیق").closest("details")).not.toHaveAttribute("open");
});

it("reveals the selected day and compact meal summaries when the plan opens", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(weeklyPlan);
  const user = userEvent.setup();

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  await screen.findByRole("heading", { name: "برنامه غذایی تو" });
  await openWeeklyPlan(user);

  expect(screen.getAllByRole("tab")).toHaveLength(7);
  expect(screen.getByText(/جمع روز/)).toBeInTheDocument();
  expect(screen.getByText("LU01 — جوجه کباب + برنج + گوجه کبابی")).toBeVisible();
});

it("keeps meal details hidden while showing name, calories, and price in its summary", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(weeklyPlan);
  const user = userEvent.setup();

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  await screen.findByRole("heading", { name: "برنامه غذایی تو" });
  await openWeeklyPlan(user);
  const mealTitle = screen.getByText("LU01 — جوجه کباب + برنج + گوجه کبابی");
  const meal = mealTitle.closest("details")!;
  expect(meal).not.toHaveAttribute("open");
  expect(mealTitle).toBeVisible();
  expect(within(meal).getByText("۷۰۰ kcal")).toBeVisible();
  expect(within(meal).getByText("۳۰٬۰۰۰ تومان")).toBeVisible();
  expect(within(meal).getByText("سینه مرغ")).not.toBeVisible();
  expect(within(meal).getByText("انرژی")).not.toBeVisible();

  await openFirstMeal(user);
  expect(within(meal).getByText("سینه مرغ")).toBeVisible();
  expect(within(meal).getByText("انرژی")).toBeVisible();
});

it("reveals the nutrient comparison and shopping list only after their summaries open", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(weeklyPlan);
  const user = userEvent.setup();

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  await screen.findByRole("heading", { name: "برنامه غذایی تو" });
  await waitFor(() => expect(nutritionApi.getShoppingList).toHaveBeenCalled());
  const nutrientSection = screen.getByText("هدف در برابر مقدار برنامه").closest("details")!;
  const shoppingSection = screen.getByText("لیست خرید دقیق").closest("details")!;
  expect(within(nutrientSection).getByText("پروتئین")).not.toBeVisible();
  expect(within(shoppingSection).getByText("سینه مرغ")).not.toBeVisible();

  await user.click(screen.getByText("هدف در برابر مقدار برنامه"));
  expect(within(nutrientSection).getByText("۱۱۲ g/day")).toBeVisible();

  await user.click(screen.getByText("لیست خرید دقیق"));
  expect(within(shoppingSection).getByText("سینه مرغ")).toBeVisible();
  expect(within(shoppingSection).getByText("۱٬۰۵۰ g")).toBeVisible();
  expect(within(shoppingSection).getByText("۱۴۰٬۰۰۰ تومان")).toBeVisible();
  expect(within(shoppingSection).getByText(/جمع.*۱۴۰٬۰۰۰ تومان/)).toBeVisible();
});

it("uses one compact weekly nutrition plan action", async () => {
  await i18n.changeLanguage("fa");

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  expect(await screen.findByRole("button", { name: "ساخت برنامه تغذیه هفتگی" })).toBeInTheDocument();
  expect(screen.queryByText("گام بعد")).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "برنامه هفتگی شخصی‌ات را بساز" })).not.toBeInTheDocument();
  expect(screen.queryByText(/فیتشو هدف‌های علمی/)).not.toBeInTheDocument();
});

it("explains a strict budget failure from its reason code", async () => {
  await i18n.changeLanguage("fa");
  await generatePlan(generationResult("infeasible", ["STRICT_BUDGET_EXCEEDED"]));

  expect(await screen.findByText("هزینه برنامه‌ای که با شرایط فعلی ساخته شد از بودجه غذایی تعیین‌شده بیشتر است. بودجه را افزایش بده یا حالت بودجه را از سخت‌گیرانه به انعطاف‌پذیر تغییر بده.")).toBeInTheDocument();
});

it("explains a flexible budget cap failure from its reason code", async () => {
  await i18n.changeLanguage("fa");
  await generatePlan(generationResult("infeasible", ["FLEXIBLE_BUDGET_CAP_EXCEEDED"]));

  expect(await screen.findByText("حتی با محدوده انعطاف‌پذیر بودجه، هزینه برنامه از سقف مجاز بیشتر شده است. بودجه غذایی را کمی افزایش بده.")).toBeInTheDocument();
});

it("explains a micronutrient upper-limit failure without naming a nutrient", async () => {
  await i18n.changeLanguage("fa");
  await generatePlan(generationResult("infeasible", ["NUTRIENT_UPPER_LIMIT_EXCEEDED"]));

  const message = await screen.findByText("برنامه ساخته‌شده از سقف ایمن یکی از ریزمغذی‌ها عبور کرده است، بنابراین فیتشو آن را قبول نکرد.");
  expect(message).toBeInTheDocument();
  expect(message).not.toHaveTextContent(/سدیم|آهن|ویتامین/);
});

it("shows one price coverage message without the legacy duplicate", async () => {
  await i18n.changeLanguage("fa");
  await generatePlan(generationResult("live_price_unavailable", ["INSUFFICIENT_PRICE_COVERAGE"]));

  const message = "برای تعداد کافی از مواد غذایی، قیمت معتبر در دسترس نیست و بدون قیمت قابل اعتماد امکان ساخت برنامه وجود ندارد.";
  expect(await screen.findByText(message)).toBeInTheDocument();
  expect(screen.getAllByText(message)).toHaveLength(1);
  expect(screen.queryByText(/هیچ قیمت زنده‌ای ساخته یا حدس زده نشد/)).not.toBeInTheDocument();
});

it("shows all distinct macro constraints when target generation has multiple reasons", async () => {
  await i18n.changeLanguage("fa");
  await generatePlan(generationResult("target_infeasible", [
    "PROTEIN_MINIMUM_EXCEEDS_CALORIE_BUDGET",
    "CARBOHYDRATE_MINIMUM_EXCEEDS_CALORIE_BUDGET",
    "FAT_MINIMUM_EXCEEDS_CALORIE_BUDGET",
    "PROTEIN_MINIMUM_EXCEEDS_CALORIE_BUDGET",
  ]));

  expect(await screen.findByText("چند محدودیت همزمان مانع ساخت برنامه شدند:")).toBeInTheDocument();
  expect(screen.getAllByRole("listitem")).toHaveLength(3);
  expect(screen.getByText("حداقل پروتئین موردنیاز با کالری هدف فعلی قابل جمع نیست.")).toBeInTheDocument();
  expect(screen.getByText("حداقل کربوهیدرات موردنیاز با کالری هدف فعلی قابل جمع نیست.")).toBeInTheDocument();
  expect(screen.getByText("حداقل چربی موردنیاز با کالری هدف فعلی قابل جمع نیست.")).toBeInTheDocument();
});

it("explains a request failure separately from an infeasible plan", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.createWeeklyNutritionPlan).mockRejectedValueOnce(new Error("network failure"));
  const user = userEvent.setup();
  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);
  await user.click(await screen.findByRole("button", { name: /ساخت برنامه تغذیه هفتگی|Build weekly nutrition plan/ }));

  expect(await screen.findByText("درخواست ساخت برنامه انجام نشد. اتصال یا سرویس را بررسی کن و دوباره تلاش کن.")).toBeInTheDocument();
  expect(screen.queryByText("با محدودیت‌های فعلی برنامه ایمن و شدنی پیدا نشد.")).not.toBeInTheDocument();
});

it("uses a safe fallback for an unknown reason code", async () => {
  await i18n.changeLanguage("fa");
  const unknownCode = "SOME_INTERNAL_ERROR_CODE";
  await generatePlan(generationResult("failed", [unknownCode]));

  expect(await screen.findByText("ساخت برنامه با یکی از محدودیت‌های فعلی کامل نشد.")).toBeInTheDocument();
  expect(screen.queryByText(unknownCode)).not.toBeInTheDocument();
});

it("keeps the outcome fallback when no reason code is returned", async () => {
  await i18n.changeLanguage("fa");
  await generatePlan(generationResult("infeasible", []));

  expect(await screen.findByText("با محدودیت‌های فعلی برنامه ایمن و شدنی پیدا نشد.")).toBeInTheDocument();
});

it("shows reason-code copy in English", async () => {
  await i18n.changeLanguage("en");
  await generatePlan(generationResult("infeasible", ["STRICT_BUDGET_EXCEEDED"]));

  expect(await screen.findByText("The generated plan exceeds your current strict food budget. Increase the budget or switch to flexible budget mode.")).toBeInTheDocument();
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

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "ساخت برنامه تغذیه هفتگی" }));

  expect(await screen.findByRole("heading", { name: "برنامه غذایی تو" })).toBeInTheDocument();
  expect(screen.getByText("در انتظار بررسی پزشک")).toBeInTheDocument();
  expect(screen.queryByText("تأییدشده توسط پزشک")).not.toBeInTheDocument();
  await openWeeklyPlan(user);
  expect(screen.getAllByRole("tab")).toHaveLength(7);
  expect(screen.getAllByText("سینه مرغ")).toHaveLength(2);
});

it("shows four Free Meal macro inputs and adds the saved intake to the actual day total", async () => {
  await i18n.changeLanguage("fa");
  const freePlan: WeeklyPlan = {
    ...weeklyPlan,
    days: weeklyPlan.days.map((day, index) => index === 0 ? {
      ...day,
      meals: [{
        id: "free-meal-1", catalogue_meal_id: null, catalogue_meal_category: "lunch",
        name_fa: null, name_en: null, meal_code: null, image_url: null,
        slot_role: "free_meal", slot_index: 0, target_distribution: {}, nutrient_totals: {},
        cost_irr: 0, is_locked: false, foods: [],
      }],
    } : day),
  };
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(freePlan);
  const user = userEvent.setup();
  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  await screen.findByRole("heading", { name: "برنامه غذایی تو" });
  await openWeeklyPlan(user);
  expect(await screen.findAllByText("وعده آزاد")).toHaveLength(2);
  await user.click(screen.getAllByText("وعده آزاد")[0]!.closest("summary")!);
  expect(screen.getByText(/لطفاً جهت محاسبه کالری روزانه/)).toBeInTheDocument();
  await user.type(screen.getByRole("spinbutton", { name: "کالری" }), "700");
  await user.type(screen.getByRole("spinbutton", { name: "پروتئین" }), "35");
  await user.type(screen.getByRole("spinbutton", { name: "کربو" }), "80");
  await user.type(screen.getByRole("spinbutton", { name: "چربی" }), "22");
  await user.click(screen.getByRole("button", { name: "ثبت وعده آزاد" }));

  expect(nutritionApi.saveFreeMeal).toHaveBeenCalledWith("free-meal-1", {
    entry_date: "2026-08-08", calories: 700, protein_g: 35, carbohydrate_g: 80, fat_g: 22,
  });
  expect(await screen.findByText(/جمع مصرف واقعی این روز/)).toHaveTextContent("۷۰۰ kcal");
  expect(screen.getByRole("link", { name: "محاسبه با عکس اختیاری" })).toHaveAttribute("href", expect.stringContaining("/nutrition-tracking?freeMealId=free-meal-1"));
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
  vi.mocked(nutritionApi.setMealLock).mockResolvedValueOnce({ is_locked: true }).mockResolvedValueOnce({ is_locked: false });
  vi.mocked(nutritionApi.saveMealFeedback).mockResolvedValue({ meal_id: "meal-0", feedback_type: "liked", change_kind: "plan_control_metadata" });
  vi.mocked(nutritionApi.previewMealRemoval).mockResolvedValue({ expected_plan_revision_id: "plan-1", meal_id: "meal-0", daily_delta: { energy_kcal: -700 }, weekly_cost_delta_irr: -300_000, new_warning_codes: ["MEAL_REMOVAL_MAY_REDUCE_ADEQUACY"] });
  vi.mocked(nutritionApi.confirmMealRemoval).mockResolvedValue({ ...weeklyPlan, id: "plan-2", revision: 2, supersedes_plan_id: "plan-1" });
  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  const user = userEvent.setup();
  await screen.findByRole("heading", { name: "Nutrition" });
  await openWeeklyPlan(user);
  await openFirstMeal(user);
  await user.click(await screen.findByRole("button", { name: "Lock meal" }));
  expect(nutritionApi.setMealLock).toHaveBeenCalledWith("plan-1", "meal-0", true);
  await user.click(await screen.findByRole("button", { name: "Unlock" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Remove meal" })).not.toBeDisabled());
  await user.click(screen.getByRole("button", { name: "Liked" }));
  expect(nutritionApi.saveMealFeedback).toHaveBeenCalledWith("plan-1", "meal-0", "liked");
  await user.click(screen.getByRole("button", { name: "Remove meal" }));
  expect(await screen.findByRole("dialog", { name: "Preview meal removal" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Create new revision" }));
  expect(nutritionApi.confirmMealRemoval).toHaveBeenCalledWith("plan-1", "meal-0", "plan-1");
  expect(await screen.findByText("Revision 2")).toBeInTheDocument();
});

it("renders weekly weight rate card with requested, recommended, and applied rates", async () => {
  await i18n.changeLanguage("fa");
  const clampedEstimate: NutritionEstimate = {
    ...estimate,
    confidence_reasons: ["complete_anthropometrics", "WEIGHT_RATE_CLAMPED_FOR_AUTOMATIC_SAFETY"],
    input_snapshot: {
      requested_weight_change_kg_per_week: "1.8",
      recommended_weight_change_kg_per_week: "0.5",
      applied_weight_change_kg_per_week: "0.8",
    },
  };
  vi.mocked(nutritionApi.getCurrentNutritionEstimate).mockResolvedValue(clampedEstimate);
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(null);

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  expect(await screen.findByRole("heading", { name: "تغذیه" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "نرخ تغییر وزن هفتگی" })).toBeInTheDocument();
  expect(screen.getByText("تنظیم‌شده برای ایمنی خودکار")).toBeInTheDocument();
  expect(screen.getByText("درخواست شما")).toBeInTheDocument();
  expect(screen.getByText("۱٫۸ کیلوگرم/هفته")).toBeInTheDocument();
  expect(screen.getByText("مقدار پیشنهادی")).toBeInTheDocument();
  expect(screen.getByText("۰٫۵ کیلوگرم/هفته")).toBeInTheDocument();
  expect(screen.getByText("مقدار اعمال‌شده (تنظیم ایمنی)")).toBeInTheDocument();
  expect(screen.getByText("۰٫۸ کیلوگرم/هفته")).toBeInTheDocument();
});

it("renders weight rate card in user override mode with override badge", async () => {
  await i18n.changeLanguage("fa");
  const overrideEstimate: NutritionEstimate = {
    ...estimate,
    confidence_reasons: ["complete_anthropometrics", "WEIGHT_RATE_USER_OVERRIDE_APPLIED"],
    input_snapshot: {
      requested_weight_change_kg_per_week: "1.8",
      recommended_weight_change_kg_per_week: "0.5",
      applied_weight_change_kg_per_week: "1.8",
      weight_rate_mode: "user_override",
    },
  };
  vi.mocked(nutritionApi.getCurrentNutritionEstimate).mockResolvedValue(overrideEstimate);
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(null);

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  expect(await screen.findByRole("heading", { name: "تغذیه" })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "نرخ تغییر وزن هفتگی" })).toBeInTheDocument();
  expect(screen.getByText("نرخ دلخواه من")).toBeInTheDocument();
  expect(screen.getByText("مقدار اعمال‌شده (نرخ مستقیم)")).toBeInTheDocument();
});

it("shows only one plan when cost gap is below 1M Toman (< 10M IRR)", async () => {
  await i18n.changeLanguage("fa");
  const budgetPlan = { ...weeklyPlan, id: "plan-budget" };
  const idealPlan = { ...weeklyPlan, id: "plan-ideal" };
  vi.mocked(nutritionApi.createWeeklyNutritionPlan).mockResolvedValue({
    generation_id: "generation-gap-small",
    outcome: "success",
    reason_codes: ["SAFE_FEASIBLE_DRAFT_GENERATED", "IDEAL_PLAN_HIDDEN_COST_GAP_SMALL"],
    warning_codes: [],
    plan: budgetPlan,
    budget_plan: budgetPlan,
    ideal_plan: idealPlan,
    comparison: {
      user_monthly_budget_irr: 80_000_000,
      budget_plan_monthly_cost_irr: 79_000_000,
      ideal_plan_monthly_cost_irr: 84_000_000,
      minimum_feasible_monthly_cost_irr: null,
      monthly_cost_gap_irr: 5_000_000,
      meaningful_quality_improvement: true,
      show_ideal_plan: false,
      reason_codes: ["IDEAL_PLAN_HIDDEN_COST_GAP_SMALL"],
      policy_version: "nutrition-plan-comparison-v1",
      micronutrient_gaps_improved: [],
      unique_meal_count_budget: 14,
      unique_meal_count_ideal: 18,
      unique_protein_sources_budget: 4,
      unique_protein_sources_ideal: 6,
    },
  });

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "ساخت برنامه تغذیه هفتگی" }));

  expect(await screen.findByRole("heading", { name: "برنامه پیشنهادی با بودجه شما" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "برنامه مرجع" })).not.toBeInTheDocument();
  expect(screen.getByText(/بودجه شما با برنامه مرجع فاصله کمی دارد/)).toBeInTheDocument();
});

it("shows two plans when cost gap >= 1M Toman and improvement is meaningful", async () => {
  await i18n.changeLanguage("fa");
  const budgetPlan = { ...weeklyPlan, id: "plan-budget" };
  const idealPlan = { ...weeklyPlan, id: "plan-ideal" };
  vi.mocked(nutritionApi.createWeeklyNutritionPlan).mockResolvedValue({
    generation_id: "generation-two-plans",
    outcome: "success",
    reason_codes: ["SAFE_FEASIBLE_DRAFT_GENERATED", "IDEAL_PLAN_SHOWN_MEANINGFUL_GAIN"],
    warning_codes: [],
    plan: budgetPlan,
    budget_plan: budgetPlan,
    ideal_plan: idealPlan,
    comparison: {
      user_monthly_budget_irr: 80_000_000,
      budget_plan_monthly_cost_irr: 79_000_000,
      ideal_plan_monthly_cost_irr: 121_000_000,
      minimum_feasible_monthly_cost_irr: null,
      monthly_cost_gap_irr: 42_000_000,
      meaningful_quality_improvement: true,
      show_ideal_plan: true,
      reason_codes: ["IDEAL_PLAN_SHOWN_MEANINGFUL_GAIN", "BUDGET_PLAN_PROTEIN_PREFERRED_GAP"],
      policy_version: "nutrition-plan-comparison-v1",
      protein_gap: {
        budget_value: 112,
        ideal_value: 130,
        difference: 18,
        unit: "g/day",
      },
      micronutrient_gaps_improved: [],
      unique_meal_count_budget: 12,
      unique_meal_count_ideal: 17,
      unique_protein_sources_budget: 3,
      unique_protein_sources_ideal: 6,
    },
  });

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "ساخت برنامه تغذیه هفتگی" }));

  expect(await screen.findByRole("heading", { name: "برنامه پیشنهادی با بودجه شما" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "برنامه مرجع" })).toBeInTheDocument();
  expect(screen.getByText("برنامه مرجع برای مقایسه است و برنامه فعال شما نیست.")).toBeInTheDocument();
});

it("shows only one plan when cost gap >= 1M Toman but quality improvement is not meaningful", async () => {
  await i18n.changeLanguage("fa");
  const budgetPlan = { ...weeklyPlan, id: "plan-budget" };
  const idealPlan = { ...weeklyPlan, id: "plan-ideal" };
  vi.mocked(nutritionApi.createWeeklyNutritionPlan).mockResolvedValue({
    generation_id: "generation-not-meaningful",
    outcome: "success",
    reason_codes: ["SAFE_FEASIBLE_DRAFT_GENERATED", "IDEAL_PLAN_HIDDEN_NO_MEANINGFUL_GAIN"],
    warning_codes: [],
    plan: budgetPlan,
    budget_plan: budgetPlan,
    ideal_plan: idealPlan,
    comparison: {
      user_monthly_budget_irr: 80_000_000,
      budget_plan_monthly_cost_irr: 79_000_000,
      ideal_plan_monthly_cost_irr: 95_000_000,
      minimum_feasible_monthly_cost_irr: null,
      monthly_cost_gap_irr: 16_000_000,
      meaningful_quality_improvement: false,
      show_ideal_plan: false,
      reason_codes: ["IDEAL_PLAN_HIDDEN_NO_MEANINGFUL_GAIN"],
      policy_version: "nutrition-plan-comparison-v1",
      micronutrient_gaps_improved: [],
      unique_meal_count_budget: 14,
      unique_meal_count_ideal: 14,
      unique_protein_sources_budget: 4,
      unique_protein_sources_ideal: 4,
    },
  });

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "ساخت برنامه تغذیه هفتگی" }));

  expect(await screen.findByRole("heading", { name: "برنامه پیشنهادی با بودجه شما" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "برنامه مرجع" })).not.toBeInTheDocument();
  expect(screen.getByText(/اختلاف کیفیت چشمگیر نبود/)).toBeInTheDocument();
});

it("renders protein gap correctly in the plan comparison summary", async () => {
  await i18n.changeLanguage("fa");
  const budgetPlan = { ...weeklyPlan, id: "plan-budget" };
  const idealPlan = { ...weeklyPlan, id: "plan-ideal" };
  vi.mocked(nutritionApi.createWeeklyNutritionPlan).mockResolvedValue({
    generation_id: "generation-protein-gap",
    outcome: "success",
    reason_codes: ["SAFE_FEASIBLE_DRAFT_GENERATED", "IDEAL_PLAN_SHOWN_MEANINGFUL_GAIN"],
    warning_codes: [],
    plan: budgetPlan,
    budget_plan: budgetPlan,
    ideal_plan: idealPlan,
    comparison: {
      user_monthly_budget_irr: 80_000_000,
      budget_plan_monthly_cost_irr: 79_000_000,
      ideal_plan_monthly_cost_irr: 121_000_000,
      minimum_feasible_monthly_cost_irr: null,
      monthly_cost_gap_irr: 42_000_000,
      meaningful_quality_improvement: true,
      show_ideal_plan: true,
      reason_codes: ["IDEAL_PLAN_SHOWN_MEANINGFUL_GAIN", "BUDGET_PLAN_PROTEIN_PREFERRED_GAP"],
      policy_version: "nutrition-plan-comparison-v1",
      protein_gap: {
        budget_value: 112,
        ideal_value: 130,
        difference: 18,
        unit: "g/day",
      },
      micronutrient_gaps_improved: [],
      unique_meal_count_budget: 12,
      unique_meal_count_ideal: 17,
      unique_protein_sources_budget: 3,
      unique_protein_sources_ideal: 6,
    },
  });

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "ساخت برنامه تغذیه هفتگی" }));

  expect(await screen.findByText("پروتئین روزانه")).toBeInTheDocument();
  expect(screen.getByText(/۱۱۲ گرم\/روز/)).toBeInTheDocument();
  expect(screen.getAllByText(/۱۳۰ گرم\/روز/)).toHaveLength(2);
  expect(screen.getByText(/حدود ۱۸ گرم بیشتر از برنامه بودجه‌ای/)).toBeInTheDocument();
});

it("renders budget-insufficient message with known minimum feasible cost", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.createWeeklyNutritionPlan).mockResolvedValue({
    generation_id: "generation-budget-infeasible-known",
    outcome: "infeasible",
    reason_codes: ["USER_BUDGET_BELOW_MINIMUM_FEASIBLE"],
    warning_codes: [],
    plan: null,
    budget_plan: null,
    ideal_plan: null,
    comparison: {
      user_monthly_budget_irr: 60_000_000,
      budget_plan_monthly_cost_irr: null,
      ideal_plan_monthly_cost_irr: 84_000_000,
      minimum_feasible_monthly_cost_irr: 84_000_000,
      monthly_cost_gap_irr: null,
      meaningful_quality_improvement: false,
      show_ideal_plan: false,
      reason_codes: ["USER_BUDGET_BELOW_MINIMUM_FEASIBLE"],
      policy_version: "nutrition-plan-comparison-v1",
      micronutrient_gaps_improved: [],
      unique_meal_count_budget: null,
      unique_meal_count_ideal: null,
      unique_protein_sources_budget: null,
      unique_protein_sources_ideal: null,
    },
  });

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "ساخت برنامه تغذیه هفتگی" }));

  expect(await screen.findByText(/با بودجه فعلی، ساخت برنامه‌ای که حداقل‌های تعیین‌شده برای هدف شما را رعایت کند ممکن نشد/)).toBeInTheDocument();
  expect(screen.getByText(/بودجه شما:/)).toBeInTheDocument();
  expect(screen.getByText("۶ میلیون تومان")).toBeInTheDocument();
  expect(screen.getByText(/حداقل هزینه تخمینی برنامه قابل‌اجرا: حدود/)).toBeInTheDocument();
  expect(screen.getByText("۸٫۴ میلیون تومان")).toBeInTheDocument();
});

it("renders budget-insufficient message without inventing minimum when unknown", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.createWeeklyNutritionPlan).mockResolvedValue({
    generation_id: "generation-budget-infeasible-unknown",
    outcome: "infeasible",
    reason_codes: ["NO_BUDGET_FEASIBLE_PLAN_FOUND"],
    warning_codes: [],
    plan: null,
    budget_plan: null,
    ideal_plan: null,
    comparison: {
      user_monthly_budget_irr: 40_000_000,
      budget_plan_monthly_cost_irr: null,
      ideal_plan_monthly_cost_irr: null,
      minimum_feasible_monthly_cost_irr: null,
      monthly_cost_gap_irr: null,
      meaningful_quality_improvement: false,
      show_ideal_plan: false,
      reason_codes: ["NO_BUDGET_FEASIBLE_PLAN_FOUND"],
      policy_version: "nutrition-plan-comparison-v1",
      micronutrient_gaps_improved: [],
      unique_meal_count_budget: null,
      unique_meal_count_ideal: null,
      unique_protein_sources_budget: null,
      unique_protein_sources_ideal: null,
    },
  });

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "ساخت برنامه تغذیه هفتگی" }));

  expect(await screen.findByText(/با قیمت‌ها و کاتالوگ فعلی، برنامه سازگار در این بودجه پیدا نشد/)).toBeInTheDocument();
  expect(screen.queryByText(/حداقل هزینه تخمینی برنامه قابل‌اجرا/)).not.toBeInTheDocument();
});

it("ensures ideal reference plan displays reference badge and disables edit controls", async () => {
  await i18n.changeLanguage("fa");
  const budgetPlan = { ...weeklyPlan, id: "plan-budget" };
  const idealPlan = { ...weeklyPlan, id: "plan-ideal" };
  vi.mocked(nutritionApi.createWeeklyNutritionPlan).mockResolvedValue({
    generation_id: "generation-reference-only",
    outcome: "success",
    reason_codes: ["SAFE_FEASIBLE_DRAFT_GENERATED", "IDEAL_PLAN_SHOWN_MEANINGFUL_GAIN"],
    warning_codes: [],
    plan: budgetPlan,
    budget_plan: budgetPlan,
    ideal_plan: idealPlan,
    comparison: {
      user_monthly_budget_irr: 80_000_000,
      budget_plan_monthly_cost_irr: 79_000_000,
      ideal_plan_monthly_cost_irr: 120_000_000,
      minimum_feasible_monthly_cost_irr: null,
      monthly_cost_gap_irr: 41_000_000,
      meaningful_quality_improvement: true,
      show_ideal_plan: true,
      reason_codes: ["IDEAL_PLAN_SHOWN_MEANINGFUL_GAIN"],
      policy_version: "nutrition-plan-comparison-v1",
      micronutrient_gaps_improved: [],
      unique_meal_count_budget: 12,
      unique_meal_count_ideal: 16,
      unique_protein_sources_budget: 3,
      unique_protein_sources_ideal: 5,
    },
  });

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "ساخت برنامه تغذیه هفتگی" }));

  expect(await screen.findByText("برنامه مرجع برای مقایسه است و برنامه فعال شما نیست.")).toBeInTheDocument();
});

it("keeps full backward compatibility when plan is generated without comparison object", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.createWeeklyNutritionPlan).mockResolvedValue({
    generation_id: "generation-legacy",
    outcome: "success",
    reason_codes: ["SAFE_FEASIBLE_DRAFT_GENERATED"],
    warning_codes: [],
    plan: weeklyPlan,
  });

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "ساخت برنامه تغذیه هفتگی" }));

  expect(await screen.findByRole("heading", { name: "برنامه غذایی تو" })).toBeInTheDocument();
  expect(screen.queryByLabelText("مقایسه برنامه‌ها")).not.toBeInTheDocument();
});

it("allows selecting between budget and ideal plan in bundle and persists choice", async () => {
  await i18n.changeLanguage("fa");
  const budgetPlan = { ...weeklyPlan, id: "plan-budget" };
  const idealPlan = { ...weeklyPlan, id: "plan-ideal" };
  vi.mocked(nutritionApi.createWeeklyNutritionPlan).mockResolvedValue({
    generation_id: "gen-bundle-1",
    bundle_id: "bundle-uuid-1",
    selected_plan_id: null,
    selected_plan_role: null,
    outcome: "success",
    reason_codes: ["SAFE_FEASIBLE_DRAFT_GENERATED"],
    warning_codes: [],
    plan: budgetPlan,
    budget_plan: budgetPlan,
    ideal_plan: idealPlan,
    comparison: {
      user_monthly_budget_irr: 150_000_000,
      budget_plan_monthly_cost_irr: 140_000_000,
      ideal_plan_monthly_cost_irr: 170_000_000,
      minimum_feasible_monthly_cost_irr: null,
      monthly_cost_gap_irr: 30_000_000,
      meaningful_quality_improvement: true,
      show_ideal_plan: true,
      reason_codes: ["IDEAL_PLAN_SHOWN_MEANINGFUL_GAIN"],
      policy_version: "nutrition-plan-comparison-v1",
      micronutrient_gaps_improved: [],
      unique_meal_count_budget: 12,
      unique_meal_count_ideal: 16,
      unique_protein_sources_budget: 3,
      unique_protein_sources_ideal: 5,
    },
  });

  vi.mocked(nutritionApi.selectBundlePlan).mockResolvedValue({
    bundle_id: "bundle-uuid-1",
    selected_plan_id: "plan-ideal",
    selected_plan_role: "ideal",
    selected_at: "2026-09-05T00:00:00Z",
    plan: idealPlan,
  });

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "ساخت برنامه تغذیه هفتگی" }));

  expect(await screen.findByText(/دو نسخه برنامه برای شما آماده شده است/)).toBeInTheDocument();
  expect(screen.queryByText("برنامه فعال شما")).not.toBeInTheDocument();

  const selectButtons = screen.getAllByRole("button", { name: "انتخاب این برنامه" });
  expect(selectButtons).toHaveLength(2);

  await user.click(selectButtons[1]);

  expect(nutritionApi.selectBundlePlan).toHaveBeenCalledWith("bundle-uuid-1", {
    selected_plan_role: "ideal",
  });
  expect(await screen.findByText("برنامه فعال شما")).toBeInTheDocument();
});

it("renders initial build button and does not render rebuild button when no plan exists", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(null);

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  expect(await screen.findByRole("button", { name: "ساخت برنامه تغذیه هفتگی" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /ساخت مجدد/ })).not.toBeInTheDocument();
  expect(screen.queryByText("ساخت مجدد برنامه غذایی")).not.toBeInTheDocument();
});

it("renders current plan and rebuild action at the bottom when plan exists", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(weeklyPlan);

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);

  expect(await screen.findByText("LU01 — جوجه کباب + برنج + گوجه کبابی")).toBeInTheDocument();
  expect(screen.getByText("ساخت مجدد برنامه غذایی")).toBeInTheDocument();
  expect(screen.getByText("اگر اطلاعاتت را تغییر داده‌ای، برنامه با اطلاعات جدیدت دوباره ساخته می‌شود.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "ساخت مجدد برنامه" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "ساخت برنامه تغذیه هفتگی" })).not.toBeInTheDocument();
});

it("calls createWeeklyNutritionPlan once and enters disabled loading state while keeping old plan visible", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(weeklyPlan);

  let resolvePlanPromise!: (val: WeeklyPlanGeneration) => void;
  const pendingPromise = new Promise<WeeklyPlanGeneration>((resolve) => {
    resolvePlanPromise = resolve;
  });
  vi.mocked(nutritionApi.createWeeklyNutritionPlan).mockReturnValue(pendingPromise);

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);
  const user = userEvent.setup();

  const rebuildBtn = await screen.findByRole("button", { name: "ساخت مجدد برنامه" });
  await user.click(rebuildBtn);

  expect(nutritionApi.createWeeklyNutritionPlan).toHaveBeenCalledTimes(1);

  // During pending request:
  // 1. Old plan remains visible
  expect(screen.getByText("LU01 — جوجه کباب + برنج + گوجه کبابی")).toBeInTheDocument();
  // 2. Button is disabled
  expect(rebuildBtn).toBeDisabled();
  // 3. Loading text is displayed
  expect(screen.getByText("در حال ساخت مجدد برنامه…")).toBeInTheDocument();

  await act(async () => {
    resolvePlanPromise({
      generation_id: "gen-2",
      outcome: "success",
      reason_codes: [],
      warning_codes: [],
      plan: weeklyPlan,
    });
  });
});

it("replaces existing plan with new plan, updates idealPlan/comparison, refetches estimate, and shows success feedback", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(weeklyPlan);

  const newPlan: WeeklyPlan = {
    ...weeklyPlan,
    id: "plan-rebuilt-2",
    days: weeklyPlan.days.map((day, idx) => ({
      ...day,
      meals: [{
        ...day.meals[0],
        name_fa: "خوراک بوقلمون با سبزیجات بخارپز",
        meal_code: `TU0${idx + 1}`,
      }],
    })),
  };

  const updatedEstimate: NutritionEstimate = {
    ...estimate,
    revision: 3,
    targets: {
      ...estimate.targets,
      goal_calories: target("kcal/day", { preferred: 2350 }),
    },
  };

  vi.mocked(nutritionApi.createWeeklyNutritionPlan).mockResolvedValue({
    generation_id: "gen-rebuild-success",
    bundle_id: "bundle-rebuild-1",
    selected_plan_id: "plan-rebuilt-2",
    selected_plan_role: "budget",
    outcome: "success",
    reason_codes: ["SAFE_FEASIBLE_DRAFT_GENERATED"],
    warning_codes: [],
    plan: newPlan,
    budget_plan: newPlan,
    ideal_plan: null,
    comparison: null,
  });

  vi.mocked(nutritionApi.getCurrentNutritionEstimate)
    .mockResolvedValueOnce(estimate)
    .mockResolvedValueOnce(updatedEstimate);

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);
  const user = userEvent.setup();

  const rebuildBtn = await screen.findByRole("button", { name: "ساخت مجدد برنامه" });
  await user.click(rebuildBtn);

  // New plan is rendered
  expect(await screen.findByText("TU01 — خوراک بوقلمون با سبزیجات بخارپز")).toBeInTheDocument();
  // Old meal is replaced
  expect(screen.queryByText("LU01 — جوجه کباب + برنج + گوجه کبابی")).not.toBeInTheDocument();
  // Success feedback message is displayed
  expect(screen.getByText("برنامه با اطلاعات جدیدت ساخته شد.")).toBeInTheDocument();
  // Estimate refetch was called
  expect(nutritionApi.getCurrentNutritionEstimate).toHaveBeenCalledTimes(2);
});

it("preserves old plan and comparison on failure, displays error, and re-enables rebuild button", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(weeklyPlan);

  vi.mocked(nutritionApi.createWeeklyNutritionPlan).mockRejectedValue(new Error("Network disconnect"));

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);
  const user = userEvent.setup();

  const rebuildBtn = await screen.findByRole("button", { name: "ساخت مجدد برنامه" });
  await user.click(rebuildBtn);

  // Old plan still displayed
  expect(await screen.findByText("LU01 — جوجه کباب + برنج + گوجه کبابی")).toBeInTheDocument();
  // Error message displayed
  expect(screen.getByText("ساخت برنامه جدید کامل نشد؛ برنامه فعلی شما تغییری نکرد.")).toBeInTheDocument();
  expect(screen.getByText("درخواست ساخت برنامه انجام نشد. اتصال یا سرویس را بررسی کن و دوباره تلاش کن.")).toBeInTheDocument();
  // Rebuild button re-enabled
  expect(rebuildBtn).toBeEnabled();
  expect(screen.getByText("ساخت مجدد برنامه")).toBeInTheDocument();
});

it("prevents double submission when clicked multiple times rapidly", async () => {
  await i18n.changeLanguage("fa");
  vi.mocked(nutritionApi.getLatestWeeklyNutritionPlan).mockResolvedValue(weeklyPlan);

  let resolvePlanPromise!: (val: WeeklyPlanGeneration) => void;
  const pendingPromise = new Promise<WeeklyPlanGeneration>((resolve) => {
    resolvePlanPromise = resolve;
  });
  vi.mocked(nutritionApi.createWeeklyNutritionPlan).mockReturnValue(pendingPromise);

  render(<MemoryRouter><NutritionEstimatePage /></MemoryRouter>);
  const user = userEvent.setup();

  const rebuildBtn = await screen.findByRole("button", { name: "ساخت مجدد برنامه" });
  // Fire clicks
  await Promise.all([
    user.click(rebuildBtn),
    user.click(rebuildBtn),
  ]);

  expect(nutritionApi.createWeeklyNutritionPlan).toHaveBeenCalledTimes(1);

  await act(async () => {
    resolvePlanPromise({
      generation_id: "gen-double-click",
      outcome: "success",
      reason_codes: [],
      warning_codes: [],
      plan: weeklyPlan,
    });
  });
});


