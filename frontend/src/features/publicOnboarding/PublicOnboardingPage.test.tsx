import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({ register: vi.fn(), login: vi.fn() }));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ ...auth, user: null, loading: false, startupError: false }),
}));

import { PublicOnboardingPage } from "./PublicOnboardingPage";
import i18n from "../../i18n";

beforeEach(async () => {
  sessionStorage.clear();
  vi.clearAllMocks();
  await i18n.changeLanguage("fa");
});

it("uses English on the first public onboarding screen when English is selected", async () => {
  await i18n.changeLanguage("en");
  render(<MemoryRouter><PublicOnboardingPage /></MemoryRouter>);

  expect(screen.getByRole("heading", { name: "What would you like help with?" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Training plan" })).toBeInTheDocument();
});

it("keeps English and asks one shared-profile question per screen", async () => {
  const user = userEvent.setup();
  await i18n.changeLanguage("en");
  render(<MemoryRouter><PublicOnboardingPage /></MemoryRouter>);

  await user.click(screen.getByRole("button", { name: "Training plan" }));
  expect(screen.getByRole("heading", { name: "What should we call you?" })).toBeInTheDocument();
  expect(screen.queryByLabelText("Birth date")).not.toBeInTheDocument();
  await user.type(screen.getByLabelText("Display name"), "Alex");
  await user.click(screen.getByRole("button", { name: "Continue" }));
  expect(screen.getByRole("heading", { name: "When were you born?" })).toBeInTheDocument();
  expect(screen.getByLabelText("Day")).toHaveClass("birth-date-picker__select");
  expect(screen.getByLabelText("Month")).toHaveClass("birth-date-picker__select");
  expect(screen.getByLabelText("Year")).toHaveClass("birth-date-picker__select");
});

it("groups height and weight with the selected valid ranges and auto-advances sex", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><PublicOnboardingPage /></MemoryRouter>);

  await user.click(screen.getByRole("button", { name: "برنامه تمرینی" }));
  await user.type(screen.getByLabelText("نام نمایشی"), "سارا");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.selectOptions(screen.getByLabelText("روز"), "14");
  await user.selectOptions(screen.getByLabelText("ماه"), "5");
  await user.selectOptions(screen.getByLabelText("سال"), "2000");
  await user.click(screen.getByRole("button", { name: "ادامه" }));

  expect(screen.getByRole("heading", { name: "جنسیتت چیست؟" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "ادامه" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "زن" }));

  expect(await screen.findByLabelText("قد (سانتی‌متر)")).toBeInTheDocument();
  expect(screen.getByLabelText("قد (سانتی‌متر)")).toHaveAttribute("min", "120");
  expect(screen.getByLabelText("قد (سانتی‌متر)")).toHaveAttribute("max", "230");
  expect(screen.getByLabelText("وزن فعلی (کیلوگرم)")).toHaveAttribute("min", "35");
  expect(screen.getByLabelText("وزن فعلی (کیلوگرم)")).toHaveAttribute("max", "300");
  await user.type(screen.getByLabelText("قد (سانتی‌متر)"), "130");
  await user.type(screen.getByLabelText("وزن فعلی (کیلوگرم)"), "36");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  expect(screen.getByLabelText("این مقادیر درست هستند.")).toBeInTheDocument();
  await user.click(screen.getByLabelText("این مقادیر درست هستند."));
  await user.click(screen.getByRole("button", { name: "ادامه" }));

  expect(await screen.findByRole("button", { name: "کاهش وزن 🔻⬆️" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "افزایش وزن 🔺️⬇️" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "چربی‌سوزی 🔥" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "عضله‌سازی 💪" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "چربی‌سوزی + عضله‌سازی 🔥💪" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "ادامه" })).not.toBeInTheDocument();
});

it("auto-advances on fitness goal and completes shared profile flow", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><PublicOnboardingPage /></MemoryRouter>);

  await user.click(screen.getByRole("button", { name: "برنامه تمرینی" }));
  await user.type(screen.getByLabelText("نام نمایشی"), "سارا");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.selectOptions(screen.getByLabelText("روز"), "14");
  await user.selectOptions(screen.getByLabelText("ماه"), "5");
  await user.selectOptions(screen.getByLabelText("سال"), "2000");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.click(screen.getByRole("button", { name: "زن" }));

  await user.type(await screen.findByLabelText("قد (سانتی‌متر)"), "165");
  await user.type(screen.getByLabelText("وزن فعلی (کیلوگرم)"), "62");
  await user.click(screen.getByRole("button", { name: "ادامه" }));

  expect(await screen.findByRole("heading", { name: "هدف اصلی تو چیست؟" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "ادامه" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "عضله‌سازی 💪" }));

  expect(await screen.findByRole("heading", { name: "چقدر سابقه تمرین مداوم داری؟" })).toBeInTheDocument();
});

it("preserves previously selected value on back navigation without auto-advancing", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><PublicOnboardingPage /></MemoryRouter>);

  await user.click(screen.getByRole("button", { name: "برنامه تمرینی" }));
  await user.type(screen.getByLabelText("نام نمایشی"), "سارا");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.selectOptions(screen.getByLabelText("روز"), "14");
  await user.selectOptions(screen.getByLabelText("ماه"), "5");
  await user.selectOptions(screen.getByLabelText("سال"), "2000");
  await user.click(screen.getByRole("button", { name: "ادامه" }));

  await user.click(screen.getByRole("button", { name: "مرد" }));
  expect(await screen.findByLabelText("قد (سانتی‌متر)")).toBeInTheDocument();

  // Go back to sex question using compact top back button
  await user.click(screen.getByRole("button", { name: "بازگشت" }));
  expect(await screen.findByRole("heading", { name: "جنسیتت چیست؟" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "مرد" })).toHaveClass("is-selected");
  // Still on sex screen; did not auto-advance merely because answer exists
  expect(screen.queryByLabelText("قد (سانتی‌متر)")).not.toBeInTheDocument();
});

it("prevents double-tap from skipping questions on single-choice options", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><PublicOnboardingPage /></MemoryRouter>);

  await user.click(screen.getByRole("button", { name: "برنامه تمرینی" }));
  await user.type(screen.getByLabelText("نام نمایشی"), "سارا");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.selectOptions(screen.getByLabelText("روز"), "14");
  await user.selectOptions(screen.getByLabelText("ماه"), "5");
  await user.selectOptions(screen.getByLabelText("سال"), "2000");
  await user.click(screen.getByRole("button", { name: "ادامه" }));

  // Rapid double-click on sex option
  const femaleBtn = screen.getByRole("button", { name: "زن" });
  await user.click(femaleBtn);
  await user.click(femaleBtn);

  // Advances to question 3 (height/weight), NOT question 4 (goal)
  expect(await screen.findByLabelText("قد (سانتی‌متر)")).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "هدف اصلی تو چیست؟" })).not.toBeInTheDocument();
});


it("starts with product mode and marks the combined path as recommended", () => {
  render(<MemoryRouter><PublicOnboardingPage /></MemoryRouter>);

  expect(screen.getByRole("heading", { name: "تو چه زمینه‌ای به کمک نیاز داری؟" })).toBeInTheDocument();
  expect(screen.getByText("پیشنهاد فیتشو")).toBeInTheDocument();
  expect(screen.queryByLabelText("ایمیل")).not.toBeInTheDocument();
});

it("shows only the three prominent product paths without explanatory copy", () => {
  render(<MemoryRouter><PublicOnboardingPage /></MemoryRouter>);

  for (const name of ["برنامه تمرینی", "برنامه تغذیه", "تمرین و تغذیه"]) {
    const option = screen.getByRole("button", { name });
    expect(option.querySelector(".product-mode-card__icon")).toBeInTheDocument();
    expect(option.querySelector(".product-mode-card__content")).toBeInTheDocument();
  }
  expect(screen.queryByText("یکی را انتخاب کن؛ فقط سؤال‌های مرتبط با همان مسیر را از تو می‌پرسیم.")).not.toBeInTheDocument();
  expect(screen.queryByText("برنامه ورزشی براساس بدن، هدف، زمان و تجهیزات")).not.toBeInTheDocument();
});

it("offers only balanced female and male choices on the gender step", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><PublicOnboardingPage /></MemoryRouter>);

  await user.click(screen.getByRole("button", { name: "برنامه تمرینی" }));
  await user.type(screen.getByLabelText("نام نمایشی"), "سارا");
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  await user.selectOptions(screen.getByLabelText("روز"), "14");
  await user.selectOptions(screen.getByLabelText("ماه"), "5");
  await user.selectOptions(screen.getByLabelText("سال"), "2000");
  await user.click(screen.getByRole("button", { name: "ادامه" }));

  const female = screen.getByRole("button", { name: "زن" });
  const male = screen.getByRole("button", { name: "مرد" });
  expect(female.parentElement).toHaveClass("guided-choice-grid--sex");
  expect(male.parentElement).toBe(female.parentElement);
  expect(screen.queryByRole("button", { name: "سایر" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "ترجیح می‌دهم نگویم" })).not.toBeInTheDocument();
});

it("lets the user go back from the first question to mode selection", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><PublicOnboardingPage /></MemoryRouter>);

  await user.click(screen.getByRole("button", { name: "برنامه تمرینی" }));
  expect(screen.getByLabelText("نام نمایشی")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "بازگشت" }));
  expect(screen.getByRole("heading", { name: "تو چه زمینه‌ای به کمک نیاز داری؟" })).toBeInTheDocument();
});

it("offers email at the final account step and labels other providers upcoming", () => {
  sessionStorage.setItem("fitsho:onboarding-draft:v1", JSON.stringify({
    mode: "training",
    training: {
      display_name: "محمد", birth_date: "2000-05-14", sex: "male", height_cm: 178,
      current_weight_kg: 76, shoulder_circumference_cm: null, waist_circumference_cm: null,
      hip_circumference_cm: null, fitness_goal: "build_muscle", experience_level: "beginner",
      training_days_per_week: 3, training_location: "gym", home_training_setup: null,
      session_duration_minutes: 60, training_cautions: [], plan_duration_weeks: 4,
    },
    readyForAuth: true,
  }));
  render(<MemoryRouter><PublicOnboardingPage /></MemoryRouter>);

  expect(screen.getByRole("heading", { name: "حالا حسابت را بساز" })).toBeInTheDocument();
  expect(screen.getByLabelText("ایمیل")).toBeEnabled();
  expect(screen.getByRole("button", { name: /Google/ })).toBeDisabled();
  expect(screen.getByRole("button", { name: /Apple/ })).toBeDisabled();
  expect(screen.getByRole("button", { name: /شماره تلفن/ })).toBeDisabled();
  expect(screen.getByRole("button", { name: "بازگشت و ویرایش پاسخ‌ها" })).toBeInTheDocument();
});
