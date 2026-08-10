import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import * as profileApi from "../profile/api";
import * as nutritionApi from "./api";
import type { SafetyDecision } from "./types";
import i18n from "../../i18n";

vi.mock("../profile/api", () => ({
  getSharedProfile: vi.fn(),
  saveSharedProfile: vi.fn(),
}));
vi.mock("./api", () => ({
  getSafetyDecision: vi.fn(),
  getNutritionProfile: vi.fn(),
  getStructuredExercise: vi.fn(),
  saveSafetyProfile: vi.fn(),
  saveNutritionProfile: vi.fn(),
  saveStructuredExercise: vi.fn(),
  createNutritionEstimate: vi.fn(),
}));

import { NutritionOnboardingFlow } from "./NutritionOnboardingFlow";

const standardDecision: SafetyDecision = {
  id: "decision-1",
  outcome: "standard_automatic",
  policy_version: "medical-condition-v1",
  reason_codes: ["no_review_condition_declared"],
  requires_physician_review: false,
  can_continue_onboarding: true,
  message: "عالی، می‌توانیم اطلاعات تغذیه‌ات را کامل کنیم.",
  created_at: "2026-08-05T12:00:00Z",
};

beforeEach(async () => {
  await i18n.changeLanguage("fa");
  vi.clearAllMocks();
  vi.mocked(profileApi.getSharedProfile).mockResolvedValue(null);
  vi.mocked(nutritionApi.getSafetyDecision).mockResolvedValue(null);
  vi.mocked(nutritionApi.getNutritionProfile).mockResolvedValue(null);
  vi.mocked(nutritionApi.getStructuredExercise).mockResolvedValue(null);
  vi.mocked(profileApi.saveSharedProfile).mockResolvedValue({
    user_id: "user-1", product_mode: "nutrition", display_name: "سارا",
    birth_date: "2000-05-14", sex: "female", height_cm: 165,
    current_weight_kg: 62.5, fitness_goal: "maintain_weight",
    weight_measured_at: "2026-08-05T12:00:00Z",
  });
  vi.mocked(nutritionApi.saveSafetyProfile).mockResolvedValue(standardDecision);
  vi.mocked(nutritionApi.saveStructuredExercise).mockResolvedValue({} as never);
  vi.mocked(nutritionApi.createNutritionEstimate).mockResolvedValue({} as never);
});

it("keeps the selected English language in the nutrition path", async () => {
  await i18n.changeLanguage("en");
  render(
    <NutritionOnboardingFlow
      productMode="nutrition"
      draftMode
      onCreateTrainingProfile={vi.fn()}
      onComplete={vi.fn()}
    />,
  );

  expect(screen.getByRole("heading", { name: "What should we call you?" })).toBeInTheDocument();
  expect(screen.getByLabelText("Display name")).toBeInTheDocument();
  expect(screen.getByLabelText("Personal details progress")).toBeInTheDocument();
});

it("asks training status and medical questions before account creation", async () => {
  await i18n.changeLanguage("en");
  const user = userEvent.setup();
  const onDraftComplete = vi.fn();
  render(
    <NutritionOnboardingFlow
      productMode="nutrition"
      draftMode
      onCreateTrainingProfile={vi.fn()}
      onComplete={vi.fn()}
      onDraftComplete={onDraftComplete}
    />,
  );

  await user.type(screen.getByLabelText("Display name"), "Sara");
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.selectOptions(screen.getByLabelText("Day"), "14");
  await user.selectOptions(screen.getByLabelText("Month"), "5");
  await user.selectOptions(screen.getByLabelText("Year"), "2000");
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.click(screen.getByRole("button", { name: "Female" }));
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.type(screen.getByLabelText("Height (centimeters)"), "165");
  await user.type(screen.getByLabelText("Current weight (kilograms)"), "62.5");
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.click(screen.getByRole("button", { name: "Fat loss 🔥" }));
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.click(screen.getByRole("button", { name: "I do not train" }));
  await user.click(screen.getByRole("button", { name: "Continue" }));

  expect(screen.getByRole("heading", { name: "Do you have any medical conditions?" })).toBeInTheDocument();
});

async function completeSharedQuestions(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("نام نمایشی"), "سارا");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.selectOptions(screen.getByLabelText("روز"), "14");
  await user.selectOptions(screen.getByLabelText("ماه"), "5");
  await user.selectOptions(screen.getByLabelText("سال"), "2000");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.click(screen.getByRole("button", { name: "زن" }));
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.type(screen.getByLabelText("قد (سانتی‌متر)"), "165");
  await user.type(screen.getByLabelText("وزن فعلی (کیلوگرم)"), "62.5");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.click(screen.getByRole("button", { name: "چربی‌سوزی 🔥" }));
  await user.click(screen.getByRole("button", { name: "ادامه" }));
}

async function reachSafety() {
  const user = userEvent.setup();
  render(
    <NutritionOnboardingFlow
      productMode="nutrition"
      onCreateTrainingProfile={vi.fn()}
      onComplete={vi.fn()}
    />,
  );
  await screen.findByRole("heading", { name: "دوست داری چه صدایت کنیم؟" });
  await completeSharedQuestions(user);
  await screen.findByRole("heading", { name: "آیا شرایط پزشکی مشخصی داری؟" });
  return user;
}

async function completeSafetyQuestions(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.click(screen.getByRole("button", { name: "رد کردن این سؤال" }));
  await user.click(screen.getByRole("button", { name: "رد کردن این سؤال" }));
  await user.click(screen.getByRole("button", { name: "رد کردن این سؤال" }));
  await user.click(screen.getByRole("button", { name: "رد کردن این سؤال" }));
}

it("saves shared data before showing the early safety screen", async () => {
  await reachSafety();

  expect(profileApi.saveSharedProfile).toHaveBeenCalledWith({
    display_name: "سارا", birth_date: "2000-05-14", sex: "female",
    height_cm: 165, current_weight_kg: 62.5, fitness_goal: "fat_loss",
  });
});

it("stops unnecessary questions for a manual-only safety outcome", async () => {
  vi.mocked(nutritionApi.saveSafetyProfile).mockResolvedValue({
    ...standardDecision,
    outcome: "physician_manual_plan_required",
    requires_physician_review: true,
    can_continue_onboarding: false,
    message: "برای حفظ ایمنی، برنامه غذایی باید توسط پزشک فیتشو تنظیم شود.",
  });
  const user = await reachSafety();
  await user.click(screen.getByLabelText("بیماری کلیه"));
  await completeSafetyQuestions(user);

  expect(await screen.findByRole("heading", { name: "ادامه مسیر با پزشک فیتشو" })).toBeInTheDocument();
  expect(screen.queryByLabelText("بودجه ماهانه غذا (تومان)")).not.toBeInTheDocument();
});

it("asks safety before training in combined mode", async () => {
  const user = userEvent.setup();
  render(
    <NutritionOnboardingFlow
      productMode="both"
      onCreateTrainingProfile={vi.fn()}
      onComplete={vi.fn()}
    />,
  );
  await screen.findByRole("heading", { name: "دوست داری چه صدایت کنیم؟" });
  await completeSharedQuestions(user);
  expect(await screen.findByRole("heading", { name: "آیا شرایط پزشکی مشخصی داری؟" })).toBeInTheDocument();

  await completeSafetyQuestions(user);
  expect(await screen.findByRole("heading", { name: "چقدر سابقه تمرین مداوم داری؟" })).toBeInTheDocument();
});

it("lets nutrition-only members opt out of training before medical questions", async () => {
  const user = userEvent.setup();
  render(<NutritionOnboardingFlow productMode="nutrition" draftMode onCreateTrainingProfile={vi.fn()} onComplete={vi.fn()} />);
  await screen.findByRole("heading", { name: "دوست داری چه صدایت کنیم؟" });
  await completeSharedQuestions(user);

  expect(await screen.findByRole("heading", { name: "در حال حاضر تمرین منظم داری؟" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "تمرین نمی‌کنم" }));
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  expect(await screen.findByRole("heading", { name: "آیا شرایط پزشکی مشخصی داری؟" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "چند روز در هفته تمرین می‌کنی؟" })).not.toBeInTheDocument();
});

it("shows essential and remaining nutrition details together after account creation", async () => {
  vi.mocked(nutritionApi.getStructuredExercise).mockResolvedValue({
    trains: false, exercise_type: null, days_per_week: null,
    minutes_per_session: null, intensity: null, source: "user_reported",
  });
  vi.mocked(nutritionApi.getNutritionProfile).mockResolvedValue({
    daily_activity_level: "moderate", individual_monthly_food_budget_irr: 13_000_000,
    budget_style: "strict", meals_per_day: 3, snacks_per_day: 1,
    preferred_plan_start_day: "saturday", plan_style: "balanced", cooking_skill: "basic",
    maximum_cooking_time_minutes: 45, cooking_frequency_per_week: 4,
    meal_preparation_preference: "mixed", refrigerator_access: true, freezer_access: true,
    cooking_equipment: ["stove", "refrigerator"], supplied_meals_per_week: 0,
    supplied_meal_source: null, foods_available_at_home: [], favourite_foods: [],
    disliked_foods: [], never_suggest_foods: [], refused_foods: [], allergies: [], intolerances: [],
    dietary_pattern: "omnivore", religious_cultural_exclusions: [], preferred_variety: "medium",
    maximum_meal_repetition_per_week: 2, accepts_leftovers: true, accepts_batch_cooking: true,
    work_shift_context: null, daily_check_in_enabled: false, preferred_check_in_time: null,
    user_id: "user-1", onboarding_status: "completed", currency: "IRR", weekly_budget_irr: 3_000_000,
    physician_review_required: false, created_at: "2026-08-05T12:00:00Z", updated_at: "2026-08-05T12:00:00Z",
  });

  render(<NutritionOnboardingFlow productMode="nutrition" editExisting onCreateTrainingProfile={vi.fn()} onComplete={vi.fn()} />);

  expect(await screen.findByRole("heading", { name: "اطلاعات تغذیه‌ای" })).toBeInTheDocument();
  expect(screen.getByLabelText("میزان فعالیت روزانه")).toHaveValue("moderate");
  expect(screen.getByLabelText("بودجه ماهانه غذا (تومان)")).toHaveValue("1,300,000");
  expect(screen.getByLabelText("الگوی غذایی")).toHaveValue("omnivore");
  expect(screen.getByLabelText("وعده اصلی در روز")).toHaveValue("3");
  expect(screen.queryByLabelText("ترجیح آماده‌سازی غذا")).not.toBeInTheDocument();
  expect(screen.queryByRole("group", { name: "تجهیزات آشپزی" })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("تنوع برنامه غذایی")).not.toBeInTheDocument();
  expect(screen.getByLabelText("غذاهایی که دوست داری (اختیاری)")).toBeInTheDocument();
  expect(screen.getByLabelText("غذاهایی که دوست نداری (اختیاری)")).toBeInTheDocument();
});

it("converts a grouped Toman budget to the existing IRR payload", async () => {
  vi.mocked(nutritionApi.saveNutritionProfile).mockResolvedValue({} as never);
  const onComplete = vi.fn();
  const user = userEvent.setup();
  render(
    <NutritionOnboardingFlow
      productMode="nutrition"
      onCreateTrainingProfile={vi.fn()}
      onComplete={onComplete}
    />,
  );
  await screen.findByRole("heading", { name: "دوست داری چه صدایت کنیم؟" });
  await completeSharedQuestions(user);
  await completeSafetyQuestions(user);

  await user.click(await screen.findByRole("button", { name: "تمرین نمی‌کنم" }));
  await user.click(screen.getByRole("button", { name: "ادامه" }));

  await user.type(await screen.findByLabelText("بودجه ماهانه غذا (تومان)"), "1300000");
  for (let index = 0; index < 5; index += 1) await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.click(screen.getByRole("button", { name: "ثبت پروفایل تغذیه" }));

  await waitFor(() => expect(nutritionApi.saveNutritionProfile).toHaveBeenCalledOnce());
  expect(nutritionApi.saveNutritionProfile).toHaveBeenCalledWith(
    expect.objectContaining({
      individual_monthly_food_budget_irr: 13_000_000,
      main_meal_count_bucket: "three_main_meals",
      snack_count_bucket: "one_snack",
    }),
  );
  const submitted = vi.mocked(nutritionApi.saveNutritionProfile).mock.calls[0][0];
  expect(submitted).not.toHaveProperty("cooking_skill");
  expect(submitted).not.toHaveProperty("meal_preparation_preference");
  expect(submitted).not.toHaveProperty("foods_available_at_home");
  expect(submitted).not.toHaveProperty("preferred_variety");
  expect(onComplete).not.toHaveBeenCalled();
  expect(screen.getByRole("heading", { name: "پروفایل تغذیه‌ات ثبت شد" })).toBeInTheDocument();
});
