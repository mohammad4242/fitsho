import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import type { Profile } from "../profile/types";

const profileApi = vi.hoisted(() => ({
  getProfile: vi.fn(),
  updateProfile: vi.fn(),
}));

vi.mock("../profile/api", () => profileApi);

import { BodyAnalysisRequirementsStep } from "./BodyAnalysisRequirementsStep";

const profile: Profile = {
  user_id: "018f0000-0000-7000-8000-000000000001",
  display_name: "Mohammad",
  birth_date: "2000-05-14",
  sex: "male",
  height_cm: 178,
  current_weight_kg: 76.5,
  weight_measured_at: "2026-07-27T12:00:00Z",
  shoulder_circumference_cm: null,
  waist_circumference_cm: null,
  hip_circumference_cm: null,
  circumferences_measured_at: null,
  fitness_goal: "build_muscle",
  experience_level: "beginner",
  training_age_months: 24,
  training_days_per_week: 3,
  preferred_weekdays: [0, 2, 4],
  priority_muscles: ["back"],
  training_location: "gym",
  home_training_setup: null,
  available_equipment: [],
  session_duration_minutes: 60,
  training_intensity: "moderate",
  physical_limitations: null,
  training_cautions: [],
  plan_duration_weeks: 4,
  created_at: "2026-07-27T12:00:00Z",
  updated_at: "2026-07-27T12:00:00Z",
};

beforeEach(async () => {
  vi.clearAllMocks();
  await i18n.changeLanguage("en");
  profileApi.getProfile.mockResolvedValue(profile);
  profileApi.updateProfile.mockResolvedValue({
    ...profile,
    shoulder_circumference_cm: 112,
    waist_circumference_cm: 82.5,
    hip_circumference_cm: 99,
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

it("requires current circumferences and an explicit confirmation before continuing", async () => {
  const user = userEvent.setup();
  const onConfirmed = vi.fn();
  render(<BodyAnalysisRequirementsStep onConfirmed={onConfirmed} onCancel={vi.fn()} />);

  const shoulder = await screen.findByLabelText(/shoulder circumference/i);
  const waist = screen.getByLabelText(/waist circumference/i);
  const hip = screen.getByLabelText(/hip circumference/i);
  const continueButton = screen.getByRole("button", { name: /continue/i });

  expect(continueButton).toBeDisabled();
  await user.type(shoulder, "112");
  await user.type(waist, "82.5");
  await user.type(hip, "99");
  expect(continueButton).toBeDisabled();

  await user.click(screen.getByRole("checkbox", { name: /measurements are current/i }));
  expect(continueButton).toBeEnabled();
  await user.click(continueButton);

  await waitFor(() => expect(profileApi.updateProfile).toHaveBeenCalledWith({
    shoulder_circumference_cm: 112,
    waist_circumference_cm: 82.5,
    hip_circumference_cm: 99,
  }));
  expect(onConfirmed).toHaveBeenCalledOnce();
});

it("does not write unchanged measurements and does not continue after a failed save", async () => {
  const user = userEvent.setup();
  const onConfirmed = vi.fn();
  profileApi.getProfile.mockResolvedValue({
    ...profile,
    shoulder_circumference_cm: 110,
    waist_circumference_cm: 82.5,
    hip_circumference_cm: 99,
  });
  profileApi.updateProfile.mockRejectedValue(new Error("offline"));
  render(<BodyAnalysisRequirementsStep onConfirmed={onConfirmed} onCancel={vi.fn()} />);

  const shoulder = await screen.findByDisplayValue("110");
  await user.clear(shoulder);
  await user.type(shoulder, "112");
  await user.click(screen.getByRole("checkbox", { name: /measurements are current/i }));
  await user.click(screen.getByRole("button", { name: /continue/i }));

  await waitFor(() => expect(onConfirmed).not.toHaveBeenCalled());
  expect(profileApi.updateProfile).toHaveBeenCalledWith({ shoulder_circumference_cm: 112 });
  expect(screen.getByRole("alert")).toBeInTheDocument();
});
