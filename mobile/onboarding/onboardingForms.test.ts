import { expect, it } from "vitest";

import {
  emptyProfileFormValues,
  profileFormValuesForSharedProfile,
  profileInputForOnboarding,
  sharedProfileInputForFormValues,
} from "./onboardingForms";

it("creates a stable empty form without sharing mutable arrays between sessions", () => {
  const first = emptyProfileFormValues();
  const second = emptyProfileFormValues();

  first.preferred_weekdays.push(1);
  expect(second.preferred_weekdays).toEqual([]);
  expect(first.plan_duration_weeks).toBe("4");
});

it("maps shared profile answers through the shared profile contract", () => {
  const values = emptyProfileFormValues();
  values.display_name = " Sara ";
  values.birth_date = "1992-05-12";
  values.sex = "female";
  values.height_cm = "168";
  values.current_weight_kg = "64";
  values.fitness_goal = "build_muscle";

  expect(sharedProfileInputForFormValues(values)).toEqual({
    birth_date: "1992-05-12",
    current_weight_kg: 64,
    display_name: "Sara",
    fitness_goal: "build_muscle",
    height_cm: 168,
    sex: "female",
  });
});

it("hydrates shared answers without inventing training answers", () => {
  const values = profileFormValuesForSharedProfile({
    birth_date: "1992-05-12",
    current_weight_kg: 64,
    display_name: "Sara",
    fitness_goal: "build_muscle",
    height_cm: 168,
    sex: "female",
  });

  expect(values.display_name).toBe("Sara");
  expect(values.training_days_per_week).toBe("");
  expect(values.training_cautions).toBeNull();
});

it("uses the shared profile validator mapping for a completed training form", () => {
  const values = {
    ...emptyProfileFormValues(),
    display_name: "Sara",
    birth_date: "1992-05-12",
    sex: "female" as const,
    height_cm: "168",
    current_weight_kg: "64",
    fitness_goal: "build_muscle" as const,
    experience_level: "beginner" as const,
    training_days_per_week: "3",
    training_location: "gym" as const,
    session_duration_minutes: "45",
    training_intensity: "moderate" as const,
    training_cautions: [],
    plan_duration_weeks: "4",
  };

  expect(profileInputForOnboarding(values, new Date("2026-09-07T00:00:00Z"))).toMatchObject({
    display_name: "Sara",
    experience_level: "beginner",
    training_days_per_week: 3,
    training_location: "gym",
  });
});
