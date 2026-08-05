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
  saveSafetyProfile: vi.fn(),
  saveNutritionProfile: vi.fn(),
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
  vi.mocked(profileApi.saveSharedProfile).mockResolvedValue({
    user_id: "user-1", product_mode: "nutrition", display_name: "سارا",
    birth_date: "2000-05-14", sex: "female", height_cm: 165,
    current_weight_kg: 62.5, fitness_goal: "maintain_weight",
    weight_measured_at: "2026-08-05T12:00:00Z",
  });
  vi.mocked(nutritionApi.saveSafetyProfile).mockResolvedValue(standardDecision);
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

it("asks medical questions before account creation", async () => {
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
  await user.click(screen.getByRole("button", { name: "ثبت ارزیابی ایمنی" }));
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
  expect(screen.queryByLabelText("بودجه ماهانه غذا (مبلغ به ریال)")).not.toBeInTheDocument();
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

it("asks the medical check before account creation in draft nutrition mode", async () => {
  const user = userEvent.setup();
  render(<NutritionOnboardingFlow productMode="nutrition" draftMode onCreateTrainingProfile={vi.fn()} onComplete={vi.fn()} />);
  await screen.findByRole("heading", { name: "دوست داری چه صدایت کنیم؟" });
  await completeSharedQuestions(user);

  expect(await screen.findByRole("heading", { name: "آیا شرایط پزشکی مشخصی داری؟" })).toBeInTheDocument();
});

it("completes the guided nutrition profile with IRR budget and optional skips", async () => {
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

  await user.type(await screen.findByLabelText("بودجه ماهانه غذا (مبلغ به ریال)"), "13000000");
  for (let index = 0; index < 6; index += 1) {
    await user.click(screen.getByRole("button", { name: "ادامه" }));
  }
  expect(screen.getByRole("heading", { name: "چقدر با آشپزی راحتی؟" })).toBeInTheDocument();
  for (let index = 0; index < 8; index += 1) {
    await user.click(screen.getByRole("button", { name: "ادامه" }));
  }
  for (let index = 0; index < 5; index += 1) {
    await user.click(screen.getByRole("button", { name: "ادامه" }));
  }
  await user.type(screen.getByLabelText("حساسیت‌های غذایی (اختیاری، با ویرگول جدا کن)"), "بادام زمینی");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  for (let index = 0; index < 8; index += 1) {
    await user.click(screen.getByRole("button", { name: "ادامه" }));
  }
  await user.click(screen.getByRole("button", { name: "مرور پاسخ‌ها" }));
  await user.click(screen.getByRole("button", { name: "ثبت پروفایل تغذیه" }));

  await waitFor(() => expect(nutritionApi.saveNutritionProfile).toHaveBeenCalledOnce());
  expect(nutritionApi.saveNutritionProfile).toHaveBeenCalledWith(
    expect.objectContaining({
      individual_monthly_food_budget_irr: 13_000_000,
      allergies: [{ name: "بادام زمینی", details: null }],
    }),
  );
  expect(onComplete).not.toHaveBeenCalled();
  expect(screen.getByRole("heading", { name: "پروفایل تغذیه‌ات ثبت شد" })).toBeInTheDocument();
});
