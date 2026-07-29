import { describe, expect, it } from "vitest";

import {
  profileToFormValues,
  toProfileInput,
  toProfilePatch,
  validateAll,
  validateStep,
} from "./profileValidation";
import type { Profile, ProfileFormValues } from "./types";

const today = new Date("2026-07-27T12:00:00Z");

const validValues: ProfileFormValues = {
  display_name: "Mohammad",
  birth_date: "2000-05-14",
  sex: "male",
  height_cm: "178",
  current_weight_kg: "76.5",
  fitness_goal: "build_muscle",
  experience_level: "beginner",
  training_days_per_week: "3",
  training_location: "gym",
  home_training_setup: "",
  session_duration_minutes: "60",
  physical_limitations: "",
  training_cautions: [],
  plan_duration_weeks: "4",
};

const profile: Profile = {
  user_id: "018f0000-0000-7000-8000-000000000001",
  display_name: "Mohammad",
  birth_date: "2000-05-14",
  sex: "male",
  height_cm: 178,
  current_weight_kg: 76.5,
  weight_measured_at: "2026-07-27T12:00:00Z",
  fitness_goal: "build_muscle",
  experience_level: "beginner",
  training_days_per_week: 3,
  training_location: "gym",
  home_training_setup: null,
  session_duration_minutes: 60,
  physical_limitations: null,
  training_cautions: [],
  plan_duration_weeks: 4,
  created_at: "2026-07-27T12:00:00Z",
  updated_at: "2026-07-27T12:00:00Z",
};

describe("profile validation", () => {
  it("catches missing, short, invalid-date, and out-of-range step-one values", () => {
    expect(
      validateStep(
        { ...validValues, display_name: " ", birth_date: "not-a-date" },
        1,
        today,
      ),
    ).toEqual({ display_name: "required", birth_date: "birthDateInvalid" });
    expect(validateStep({ ...validValues, display_name: "M" }, 1, today)).toEqual({
      display_name: "displayNameLength",
    });
    expect(validateStep({ ...validValues, birth_date: "2009-07-28" }, 1, today)).toEqual({
      birth_date: "ageRange",
    });
    expect(validateStep({ ...validValues, birth_date: "1925-07-27" }, 1, today)).toEqual({
      birth_date: "ageRange",
    });
  });

  it("catches regressions at exact valid age boundaries", () => {
    expect(validateStep({ ...validValues, birth_date: "2008-07-27" }, 1, today)).toEqual({});
    expect(validateStep({ ...validValues, birth_date: "1926-07-27" }, 1, today)).toEqual({});
  });

  it("catches changed height and weight boundaries or weight precision", () => {
    expect(
      validateStep(
        { ...validValues, height_cm: "100", current_weight_kg: "20" },
        2,
        today,
      ),
    ).toEqual({});
    expect(
      validateStep(
        { ...validValues, height_cm: "250", current_weight_kg: "500" },
        2,
        today,
      ),
    ).toEqual({});
    expect(validateStep({ ...validValues, height_cm: "99" }, 2, today)).toEqual({
      height_cm: "heightRange",
    });
    expect(validateStep({ ...validValues, height_cm: "251" }, 2, today)).toEqual({
      height_cm: "heightRange",
    });
    expect(validateStep({ ...validValues, current_weight_kg: "19.99" }, 2, today)).toEqual({
      current_weight_kg: "weightRange",
    });
    expect(validateStep({ ...validValues, current_weight_kg: "500.01" }, 2, today)).toEqual({
      current_weight_kg: "weightRange",
    });
    expect(validateStep({ ...validValues, current_weight_kg: "76.123" }, 2, today)).toEqual({
      current_weight_kg: "weightPrecision",
    });
  });

  it("requires the fitness goal on the body and goal step", () => {
    expect(validateStep({ ...validValues, fitness_goal: "" }, 2, today)).toEqual({
      fitness_goal: "required",
    });
  });

  it("catches invalid training days and overlong limitations", () => {
    expect(validateStep({ ...validValues, training_days_per_week: "0" }, 3, today)).toEqual({
      training_days_per_week: "trainingDaysRange",
    });
    expect(validateStep({ ...validValues, training_days_per_week: "8" }, 3, today)).toEqual({
      training_days_per_week: "trainingDaysRange",
    });
    expect(
      validateStep({ ...validValues, physical_limitations: "x".repeat(1001) }, 3, today),
    ).toEqual({ physical_limitations: "limitationsLength" });
  });

  it("requires a home setup only for home training and accepts supported durations", () => {
    expect(
      validateStep(
        { ...validValues, training_location: "home", home_training_setup: "" },
        3,
        today,
      ),
    ).toEqual({ home_training_setup: "required" });
    expect(
      validateStep({ ...validValues, session_duration_minutes: "50" }, 3, today),
    ).toEqual({ session_duration_minutes: "sessionDurationInvalid" });
    expect(
      validateStep(
        {
          ...validValues,
          training_location: "home",
          home_training_setup: "dumbbells_available",
          session_duration_minutes: "90",
        },
        3,
        today,
      ),
    ).toEqual({});
  });

  it("catches failures from every validation step", () => {
    expect(
      validateAll(
        {
          ...validValues,
          display_name: "",
          height_cm: "99",
          training_days_per_week: "8",
        },
        today,
      ),
    ).toEqual({
      display_name: "required",
      height_cm: "heightRange",
      training_days_per_week: "trainingDaysRange",
    });
  });

  it("catches skipped normalization while converting valid form values", () => {
    expect(
      toProfileInput({
        ...validValues,
        display_name: "  Mohammad  ",
        height_cm: " 178 ",
        current_weight_kg: " 76.5 ",
        training_days_per_week: " 3 ",
        physical_limitations: "   ",
      }),
    ).toEqual({
      display_name: "Mohammad",
      birth_date: "2000-05-14",
      sex: "male",
      height_cm: 178,
      current_weight_kg: 76.5,
      fitness_goal: "build_muscle",
      experience_level: "beginner",
      training_days_per_week: 3,
      training_location: "gym",
      home_training_setup: null,
      session_duration_minutes: 60,
      physical_limitations: null,
  training_cautions: [],
  plan_duration_weeks: 4,
    });
  });

  it("converts a saved profile into editable string values", () => {
    expect(profileToFormValues(profile)).toEqual(validValues);
  });

  it("catches emitting unchanged fields or omitting changed fields in patches", () => {
    expect(toProfilePatch(validValues, profile)).toEqual({});
    expect(
      toProfilePatch(
        { ...validValues, display_name: "  Mo  ", current_weight_kg: "75.25" },
        profile,
      ),
    ).toEqual({ display_name: "Mo", current_weight_kg: 75.25 });
  });

  it("serializes workout preference changes", () => {
    expect(
      toProfilePatch(
        {
          ...validValues,
          training_location: "home",
          home_training_setup: "bodyweight_only",
          session_duration_minutes: "75",
        },
        profile,
      ),
    ).toEqual({
      training_location: "home",
      home_training_setup: "bodyweight_only",
      session_duration_minutes: 75,
    });
  });
});
