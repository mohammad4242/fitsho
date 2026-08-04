import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import * as profileApi from "../profile/api";
import * as nutritionApi from "./api";
import type { SafetyDecision } from "./types";

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

beforeEach(() => {
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

async function reachSafety() {
  const user = userEvent.setup();
  render(
    <NutritionOnboardingFlow
      productMode="nutrition"
      onCreateTrainingProfile={vi.fn()}
      onComplete={vi.fn()}
    />,
  );
  await screen.findByRole("heading", { name: "اول کمی با هم آشنا شویم" });
  await user.type(screen.getByLabelText("نام نمایشی"), "سارا");
  await user.type(screen.getByLabelText("تاریخ تولد"), "2000-05-14");
  await user.selectOptions(screen.getByLabelText("جنسیت"), "female");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.type(screen.getByLabelText("قد (سانتی‌متر)"), "165");
  await user.type(screen.getByLabelText("وزن فعلی (کیلوگرم)"), "62.5");
  await user.selectOptions(screen.getByLabelText("هدف ورزشی"), "maintain_weight");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await screen.findByRole("heading", { name: "اول ایمنی، بعد برنامه" });
  return user;
}

it("saves shared data before showing the early safety screen", async () => {
  await reachSafety();

  expect(profileApi.saveSharedProfile).toHaveBeenCalledWith({
    display_name: "سارا", birth_date: "2000-05-14", sex: "female",
    height_cm: 165, current_weight_kg: 62.5, fitness_goal: "maintain_weight",
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
  await user.click(screen.getByRole("button", { name: "ثبت ارزیابی ایمنی" }));

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
  await screen.findByRole("heading", { name: "اول کمی با هم آشنا شویم" });
  await user.type(screen.getByLabelText("نام نمایشی"), "سارا");
  await user.type(screen.getByLabelText("تاریخ تولد"), "2000-05-14");
  await user.selectOptions(screen.getByLabelText("جنسیت"), "female");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.type(screen.getByLabelText("قد (سانتی‌متر)"), "165");
  await user.type(screen.getByLabelText("وزن فعلی (کیلوگرم)"), "62.5");
  await user.selectOptions(screen.getByLabelText("هدف ورزشی"), "maintain_weight");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  expect(await screen.findByRole("heading", { name: "اول ایمنی، بعد برنامه" })).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "ثبت ارزیابی ایمنی" }));
  expect(await screen.findByRole("heading", { name: "حالا بخش تمرین را هماهنگ کنیم" })).toBeInTheDocument();
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
  await screen.findByRole("heading", { name: "اول کمی با هم آشنا شویم" });
  await user.type(screen.getByLabelText("نام نمایشی"), "سارا");
  await user.type(screen.getByLabelText("تاریخ تولد"), "2000-05-14");
  await user.selectOptions(screen.getByLabelText("جنسیت"), "female");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.type(screen.getByLabelText("قد (سانتی‌متر)"), "165");
  await user.type(screen.getByLabelText("وزن فعلی (کیلوگرم)"), "62.5");
  await user.selectOptions(screen.getByLabelText("هدف ورزشی"), "maintain_weight");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.click(screen.getByRole("button", { name: "ثبت ارزیابی ایمنی" }));

  await user.type(await screen.findByLabelText("بودجه ماهانه غذا (مبلغ به ریال)"), "13000000");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  expect(screen.getByRole("heading", { name: "آشپزی را با زندگی تو هماهنگ می‌کنیم" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.type(screen.getByLabelText("حساسیت‌های غذایی (اختیاری، با ویرگول جدا کن)"), "بادام زمینی");
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
