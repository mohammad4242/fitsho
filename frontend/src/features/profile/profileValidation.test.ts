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
  shoulder_circumference_cm: "",
  waist_circumference_cm: "",
  hip_circumference_cm: "",
  fitness_goal: "build_muscle",
  experience_level: "beginner",
  training_age_months: "24",
  training_days_per_week: "3",
  preferred_weekdays: [0, 2, 4],
  priority_muscle: "back",
  training_location: "gym",
  home_training_setup: "",
  available_equipment: [],
  session_duration_minutes: "60",
  training_intensity: "moderate",
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

  it("validates optional training age when it is supplied", () => {
    expect(
      validateStep({ ...validValues, training_age_months: "901" }, 3, today),
    ).toEqual({ training_age_months: "trainingAgeRange" });
  });

  it("catches regressions at exact valid age boundaries", () => {
    expect(validateStep({ ...validValues, birth_date: "2008-07-27" }, 1, today)).toEqual({});
    expect(validateStep({ ...validValues, birth_date: "1926-07-27" }, 1, today)).toEqual({});
  });

  it("accepts the selected height and weight boundaries and rejects values outside them", () => {
    expect(
      validateStep(
        { ...validValues, height_cm: "120", current_weight_kg: "35" },
        2,
        today,
      ),
    ).toEqual({});
    expect(
      validateStep(
        { ...validValues, height_cm: "230", current_weight_kg: "300" },
        2,
        today,
      ),
    ).toEqual({});
    expect(validateStep({ ...validValues, height_cm: "119" }, 2, today)).toEqual({
      height_cm: "heightRange",
    });
    expect(validateStep({ ...validValues, height_cm: "231" }, 2, today)).toEqual({
      height_cm: "heightRange",
    });
    expect(validateStep({ ...validValues, current_weight_kg: "34.99" }, 2, today)).toEqual({
      current_weight_kg: "weightRange",
    });
    expect(validateStep({ ...validValues, current_weight_kg: "300.01" }, 2, today)).toEqual({
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

  it("accepts blank optional circumferences and validates supplied values", () => {
    expect(validateStep(validValues, 2, today)).toEqual({});
    expect(
      validateStep(
        { ...validValues, shoulder_circumference_cm: "39.99", hip_circumference_cm: "98.123" },
        2,
        today,
      ),
    ).toEqual({
      shoulder_circumference_cm: "circumferenceRange",
      hip_circumference_cm: "circumferencePrecision",
    });
  });

  it("accepts only two through six training days", () => {
    expect(validateStep({ ...validValues, training_days_per_week: "6" }, 3, today)).toEqual({});
    expect(validateStep({ ...validValues, training_days_per_week: "1" }, 3, today)).toEqual({
      training_days_per_week: "trainingDaysRange",
    });
    expect(validateStep({ ...validValues, training_days_per_week: "7" }, 3, today)).toEqual({
      training_days_per_week: "trainingDaysRange",
    });
  });

  it("limits preferred weekdays to the configured training days", () => {
    expect(
      validateStep({ ...validValues, training_days_per_week: "2" }, 3, today),
    ).toEqual({ preferred_weekdays: "preferredWeekdaysInvalid" });
    expect(
      validateStep({ ...validValues, training_days_per_week: "3" }, 3, today),
    ).toEqual({});
  });

  it("requires a non-empty home inventory and accepts supported durations", () => {
    expect(
      validateStep(
        { ...validValues, training_location: "home", available_equipment: [] },
        3,
        today,
      ),
    ).toEqual({ available_equipment: "required" });
    expect(
      validateStep({ ...validValues, session_duration_minutes: "50" }, 3, today),
    ).toEqual({ session_duration_minutes: "sessionDurationInvalid" });
    expect(
      validateStep(
        {
          ...validValues,
          training_location: "home",
          available_equipment: ["bodyweight", "dumbbell", "bench"],
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
        shoulder_circumference_cm: " 122.5 ",
        waist_circumference_cm: " 84 ",
        hip_circumference_cm: " 98.25 ",
        training_days_per_week: " 3 ",
      }),
    ).toEqual({
      display_name: "Mohammad",
      birth_date: "2000-05-14",
      sex: "male",
      height_cm: 178,
      current_weight_kg: 76.5,
      shoulder_circumference_cm: 122.5,
      waist_circumference_cm: 84,
      hip_circumference_cm: 98.25,
      fitness_goal: "build_muscle",
      experience_level: "beginner",
      training_age_months: 24,
      training_days_per_week: 3,
      preferred_weekdays: [0, 2, 4],
      priority_muscles: ["back"],
      training_location: "gym",
      home_training_setup: null,
      available_equipment: null,
      session_duration_minutes: 60,
      training_intensity: "moderate",
      training_cautions: [],
      plan_duration_weeks: 4,
    });
  });

  it("does not serialize legacy free-text limitations", () => {
    expect(toProfileInput(validValues)).not.toHaveProperty("physical_limitations");
  });

  it("serializes no focus as null and one focus as a one-item wire list", () => {
    expect(toProfileInput({ ...validValues, priority_muscle: "" }).priority_muscles).toBeNull();
    expect(toProfileInput({ ...validValues, priority_muscle: "chest" }).priority_muscles).toEqual([
      "chest",
    ]);
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
          available_equipment: ["bodyweight", "bench"],
          session_duration_minutes: "75",
        },
        profile,
      ),
    ).toEqual({
      training_location: "home",
      available_equipment: ["bodyweight", "bench"],
      session_duration_minutes: 75,
    });
  });

  it("derives the legacy home setup from canonical equipment", () => {
    expect(
      toProfileInput({
        ...validValues,
        training_location: "home",
        available_equipment: ["dumbbell", "bodyweight", "dumbbell"],
      }),
    ).toMatchObject({
      home_training_setup: "dumbbells_available",
      available_equipment: ["bodyweight", "dumbbell"],
    });
    expect(
      toProfileInput({
        ...validValues,
        training_location: "home",
        available_equipment: ["bodyweight"],
      }).home_training_setup,
    ).toBe("bodyweight_only");
    expect(
      toProfileInput({
        ...validValues,
        training_location: "home",
        available_equipment: ["bodyweight", "bench"],
      }).home_training_setup,
    ).toBeNull();
  });

  it("serializes training age changes", () => {
    expect(
      toProfilePatch({ ...validValues, training_age_months: "48" }, profile),
    ).toEqual({ training_age_months: 48 });
  });
});
