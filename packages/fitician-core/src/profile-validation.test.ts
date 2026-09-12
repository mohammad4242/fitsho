import { expect, it } from "vitest";

import {
  toProfileInput,
  validateStep,
} from "./profile-validation.js";
import type { ProfileFormValues } from "./profile.js";

const today = new Date("2026-09-12T12:00:00Z");
const baseValues: ProfileFormValues = {
  display_name: "Member",
  birth_date: "1990-01-01",
  sex: "male",
  height_cm: "180",
  current_weight_kg: "80",
  shoulder_circumference_cm: "",
  waist_circumference_cm: "",
  hip_circumference_cm: "",
  fitness_goal: "build_muscle",
  experience_level: "beginner",
  training_age_months: "12",
  training_days_per_week: "3",
  preferred_weekdays: [0, 2, 4],
  priority_muscle: "",
  training_location: "home",
  home_training_setup: "bodyweight_only",
  available_equipment: ["bodyweight"],
  session_duration_minutes: "60",
  training_intensity: "moderate",
  training_cautions: [],
  plan_duration_weeks: "4",
};

const expectedEquipment = {
  bodyweight_only: ["bodyweight", "pull_up_bar"],
  dumbbells_available: ["bodyweight", "dumbbell", "pull_up_bar"],
  resistance_bands_available: ["bodyweight", "resistance_band", "pull_up_bar"],
  dumbbells_and_resistance_bands_available: [
    "bodyweight",
    "dumbbell",
    "resistance_band",
    "pull_up_bar",
  ],
} as const;

it("serializes each home preset to its canonical inventory", () => {
  for (const [setup, equipment] of Object.entries(expectedEquipment)) {
    expect(
      toProfileInput({
        ...baseValues,
        home_training_setup: setup as ProfileFormValues["home_training_setup"],
        available_equipment: ["bodyweight"],
      }),
    ).toMatchObject({
      home_training_setup: setup,
      available_equipment: equipment,
    });
  }
});

it("requires a valid home preset even when legacy equipment is present", () => {
  expect(
    validateStep(
      { ...baseValues, home_training_setup: "", available_equipment: ["bodyweight"] },
      3,
      today,
    ),
  ).toEqual({ available_equipment: "required" });
});

it("keeps gym serialization free of home setup and equipment", () => {
  expect(
    toProfileInput({
      ...baseValues,
      training_location: "gym",
      home_training_setup: "",
      available_equipment: ["bodyweight", "dumbbell"],
    }),
  ).toMatchObject({
    training_location: "gym",
    home_training_setup: null,
    available_equipment: null,
  });
});
