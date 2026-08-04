import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({ register: vi.fn(), login: vi.fn() }));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ ...auth, user: null, loading: false, startupError: false }),
}));

import { PublicOnboardingPage } from "./PublicOnboardingPage";

beforeEach(() => {
  sessionStorage.clear();
  vi.clearAllMocks();
});

it("starts with product mode and marks the combined path as recommended", () => {
  render(<MemoryRouter><PublicOnboardingPage /></MemoryRouter>);

  expect(screen.getByRole("heading", { name: "تو چه زمینه‌ای به کمک نیاز داری؟" })).toBeInTheDocument();
  expect(screen.getByText("پیشنهاد فیتشو")).toBeInTheDocument();
  expect(screen.queryByLabelText("ایمیل")).not.toBeInTheDocument();
});

it("shows only the three prominent product paths without explanatory copy", () => {
  render(<MemoryRouter><PublicOnboardingPage /></MemoryRouter>);

  expect(screen.getByRole("button", { name: "برنامه تمرینی" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "برنامه تغذیه" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "تمرین و تغذیه" })).toBeInTheDocument();
  expect(screen.queryByText("یکی را انتخاب کن؛ فقط سؤال‌های مرتبط با همان مسیر را از تو می‌پرسیم.")).not.toBeInTheDocument();
  expect(screen.queryByText("برنامه ورزشی براساس بدن، هدف، زمان و تجهیزات")).not.toBeInTheDocument();
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
      session_duration_minutes: 60, physical_limitations: null, training_cautions: [], plan_duration_weeks: 4,
    },
    readyForAuth: true,
  }));
  render(<MemoryRouter><PublicOnboardingPage /></MemoryRouter>);

  expect(screen.getByRole("heading", { name: "حالا حسابت را بساز" })).toBeInTheDocument();
  expect(screen.getByLabelText("ایمیل")).toBeEnabled();
  expect(screen.getByRole("button", { name: /Google/ })).toBeDisabled();
  expect(screen.getByRole("button", { name: /Apple/ })).toBeDisabled();
  expect(screen.getByRole("button", { name: /شماره تلفن/ })).toBeDisabled();
});
