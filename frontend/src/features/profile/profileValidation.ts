import {
  sessionDurations,
  type ExperienceLevel,
  availableEquipment,
  type Equipment,
  type FitnessGoal,
  type HomeTrainingSetup,
  type Profile,
  type ProfileFormValues,
  type ProfileInput,
  type ProfilePatch,
  type PlanDurationWeeks,
  type SessionDurationMinutes,
  type TrainingCaution,
  type Sex,
  type TrainingLocation,
} from "./types";

export type ProfileValidationCode =
  | "required"
  | "displayNameLength"
  | "birthDateInvalid"
  | "ageRange"
  | "heightRange"
  | "weightRange"
  | "weightPrecision"
  | "circumferenceRange"
  | "circumferencePrecision"
  | "trainingDaysRange"
  | "trainingAgeRange"
  | "preferredWeekdaysInvalid"
  | "sessionDurationInvalid"
  | "planDurationInvalid";

export type ProfileValidationErrors = Partial<
  Record<keyof ProfileFormValues, ProfileValidationCode>
>;

function parseBirthDate(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (match === null) {
    return null;
  }

  const [, yearValue, monthValue, dayValue] = match;
  const year = Number(yearValue);
  const month = Number(monthValue);
  const day = Number(dayValue);
  const date = new Date(0);
  date.setUTCFullYear(year, month - 1, day);
  date.setUTCHours(0, 0, 0, 0);

  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return null;
  }
  return date;
}

function ageOn(birthDate: Date, today: Date): number {
  return (
    today.getUTCFullYear() -
    birthDate.getUTCFullYear() -
    (today.getUTCMonth() < birthDate.getUTCMonth() ||
    (today.getUTCMonth() === birthDate.getUTCMonth() &&
      today.getUTCDate() < birthDate.getUTCDate())
      ? 1
      : 0)
  );
}

function validateStepOne(
  values: ProfileFormValues,
  today: Date,
): ProfileValidationErrors {
  const errors: ProfileValidationErrors = {};
  const displayName = values.display_name.trim();
  if (displayName === "") {
    errors.display_name = "required";
  } else if (displayName.length < 2 || displayName.length > 80) {
    errors.display_name = "displayNameLength";
  }

  if (values.birth_date.trim() === "") {
    errors.birth_date = "required";
  } else {
    const birthDate = parseBirthDate(values.birth_date);
    if (birthDate === null) {
      errors.birth_date = "birthDateInvalid";
    } else if (ageOn(birthDate, today) < 18 || ageOn(birthDate, today) > 100) {
      errors.birth_date = "ageRange";
    }
  }

  if (values.sex === "") {
    errors.sex = "required";
  }
  return errors;
}

function validateStepTwo(values: ProfileFormValues): ProfileValidationErrors {
  const errors: ProfileValidationErrors = {};
  const height = values.height_cm.trim();
  if (height === "") {
    errors.height_cm = "required";
  } else if (!/^\d+$/.test(height) || Number(height) < 120 || Number(height) > 230) {
    errors.height_cm = "heightRange";
  }

  for (const field of [
    "shoulder_circumference_cm",
    "waist_circumference_cm",
    "hip_circumference_cm",
  ] as const) {
    const value = values[field].trim();
    if (value === "") {
      continue;
    }
    const match = /^-?\d+(?:\.(\d+))?$/.exec(value);
    const numericValue = Number(value);
    if (match === null || !Number.isFinite(numericValue) || numericValue < 40 || numericValue > 250) {
      errors[field] = "circumferenceRange";
    } else if ((match[1]?.length ?? 0) > 2) {
      errors[field] = "circumferencePrecision";
    }
  }

  const weight = values.current_weight_kg.trim();
  if (weight === "") {
    errors.current_weight_kg = "required";
  } else {
    const match = /^-?\d+(?:\.(\d+))?$/.exec(weight);
    const numericWeight = Number(weight);
    if (match === null || !Number.isFinite(numericWeight)) {
      errors.current_weight_kg = "weightRange";
    } else if ((match[1]?.length ?? 0) > 2) {
      errors.current_weight_kg = "weightPrecision";
    } else if (numericWeight < 35 || numericWeight > 300) {
      errors.current_weight_kg = "weightRange";
    }
  }
  if (values.fitness_goal === "") {
    errors.fitness_goal = "required";
  }
  return errors;
}

function validateStepThree(values: ProfileFormValues): ProfileValidationErrors {
  const errors: ProfileValidationErrors = {};
  if (values.experience_level === "") {
    errors.experience_level = "required";
  }

  const trainingDays = values.training_days_per_week.trim();
  if (trainingDays === "") {
    errors.training_days_per_week = "required";
  } else if (
    !/^\d+$/.test(trainingDays) ||
    Number(trainingDays) < 2 ||
    Number(trainingDays) > 6
  ) {
    errors.training_days_per_week = "trainingDaysRange";
  }

  if (
    values.preferred_weekdays.length > 0 &&
    trainingDays !== "" &&
    Number.isInteger(Number(trainingDays)) &&
    Number(trainingDays) >= 2 &&
    Number(trainingDays) <= 6 &&
    values.preferred_weekdays.length > Number(trainingDays)
  ) {
    errors.preferred_weekdays = "preferredWeekdaysInvalid";
  }

  const trainingAge = values.training_age_months.trim();
  if (
    trainingAge !== "" &&
    (!/^\d+$/.test(trainingAge) || Number(trainingAge) > 900)
  ) {
    errors.training_age_months = "trainingAgeRange";
  }

  if (values.training_location === "") {
    errors.training_location = "required";
  }
  if (
    values.training_location === "home" &&
    (values.available_equipment === undefined
      ? values.home_training_setup === ""
      : values.available_equipment.length === 0)
  ) {
    errors.available_equipment = "required";
  }

  const sessionDuration = values.session_duration_minutes.trim();
  if (sessionDuration === "") {
    errors.session_duration_minutes = "required";
  } else if (
    !sessionDurations.some((duration) => duration === Number(sessionDuration))
  ) {
    errors.session_duration_minutes = "sessionDurationInvalid";
  }

  if (values.training_cautions === null) {
    errors.training_cautions = "required";
  }

  if (values.training_intensity === "") {
    errors.training_intensity = "required";
  }

  const planDuration = values.plan_duration_weeks.trim();
  if (planDuration === "") {
    errors.plan_duration_weeks = "required";
  } else if (![4, 6, 8].includes(Number(planDuration))) {
    errors.plan_duration_weeks = "planDurationInvalid";
  }

  return errors;
}

export function validateStep(
  values: ProfileFormValues,
  step: 1 | 2 | 3,
  today: Date,
): ProfileValidationErrors {
  if (step === 1) {
    return validateStepOne(values, today);
  }
  if (step === 2) {
    return validateStepTwo(values);
  }
  return validateStepThree(values);
}

export function validateAll(
  values: ProfileFormValues,
  today: Date,
): ProfileValidationErrors {
  return {
    ...validateStepOne(values, today),
    ...validateStepTwo(values),
    ...validateStepThree(values),
  };
}

export function toProfileInput(values: ProfileFormValues): ProfileInput {
  const normalizedEquipment = normalizeEquipment(values.available_equipment ?? []);
  const homeEquipment = values.training_location === "home"
    ? values.available_equipment === undefined
      ? legacySetupEquipment(values.home_training_setup)
      : normalizedEquipment
    : null;
  const homeTrainingSetup = deriveHomeTrainingSetup(homeEquipment);
  return {
    display_name: values.display_name.trim(),
    birth_date: values.birth_date.trim(),
    sex: values.sex as Sex,
    height_cm: Number(values.height_cm.trim()),
    current_weight_kg: Number(values.current_weight_kg.trim()),
    shoulder_circumference_cm: values.shoulder_circumference_cm.trim()
      ? Number(values.shoulder_circumference_cm.trim())
      : null,
    waist_circumference_cm: values.waist_circumference_cm.trim()
      ? Number(values.waist_circumference_cm.trim())
      : null,
    hip_circumference_cm: values.hip_circumference_cm.trim()
      ? Number(values.hip_circumference_cm.trim())
      : null,
    fitness_goal: values.fitness_goal as FitnessGoal,
    experience_level: values.experience_level as ExperienceLevel,
    training_age_months: values.training_age_months.trim()
      ? Number(values.training_age_months.trim())
      : null,
    training_days_per_week: Number(values.training_days_per_week.trim()),
    preferred_weekdays: values.preferred_weekdays.length > 0
      ? [...values.preferred_weekdays]
      : null,
    priority_muscles: values.priority_muscle !== ""
      ? [values.priority_muscle]
      : null,
    training_location: values.training_location as TrainingLocation,
    home_training_setup:
      homeTrainingSetup,
    available_equipment: homeEquipment,
    session_duration_minutes: Number(
      values.session_duration_minutes,
    ) as SessionDurationMinutes,
    training_intensity: values.training_intensity as ProfileInput["training_intensity"],
    training_cautions: values.training_cautions as TrainingCaution[],
    plan_duration_weeks: Number(values.plan_duration_weeks) as PlanDurationWeeks,
  };
}

export function profileToFormValues(profile: Profile): ProfileFormValues {
  return {
    display_name: profile.display_name,
    birth_date: profile.birth_date,
    sex: profile.sex,
    height_cm: String(profile.height_cm),
    current_weight_kg: String(profile.current_weight_kg),
    shoulder_circumference_cm: profile.shoulder_circumference_cm === null ? "" : String(profile.shoulder_circumference_cm),
    waist_circumference_cm: profile.waist_circumference_cm === null ? "" : String(profile.waist_circumference_cm),
    hip_circumference_cm: profile.hip_circumference_cm === null ? "" : String(profile.hip_circumference_cm),
    fitness_goal: profile.fitness_goal,
    experience_level: profile.experience_level,
    training_age_months: profile.training_age_months == null
      ? ""
      : String(profile.training_age_months),
    training_days_per_week: String(profile.training_days_per_week),
    preferred_weekdays: [...(profile.preferred_weekdays ?? [])].sort((a, b) => a - b),
    priority_muscle: profile.priority_muscles?.length === 1
      ? profile.priority_muscles[0]
      : "",
    training_location: profile.training_location,
    home_training_setup: profile.home_training_setup ?? "",
    available_equipment: profile.available_equipment === null
      ? legacySetupEquipment(profile.home_training_setup ?? "")
      : [...(profile.available_equipment ?? [])],
    session_duration_minutes: String(profile.session_duration_minutes),
    training_intensity: profile.training_intensity ?? "",
    training_cautions: profile.training_cautions,
    plan_duration_weeks: String(profile.plan_duration_weeks),
  };
}

export function toProfilePatch(
  values: ProfileFormValues,
  currentProfile: Profile,
): ProfilePatch {
  const input = toProfileInput(values);
  const patch: ProfilePatch = {};

  if (input.display_name !== currentProfile.display_name) {
    patch.display_name = input.display_name;
  }
  if (input.birth_date !== currentProfile.birth_date) {
    patch.birth_date = input.birth_date;
  }
  if (input.sex !== currentProfile.sex) {
    patch.sex = input.sex;
  }
  if (input.height_cm !== currentProfile.height_cm) {
    patch.height_cm = input.height_cm;
  }
  if (input.current_weight_kg !== currentProfile.current_weight_kg) {
    patch.current_weight_kg = input.current_weight_kg;
  }
  for (const field of [
    "shoulder_circumference_cm",
    "waist_circumference_cm",
    "hip_circumference_cm",
  ] as const) {
    if (input[field] !== currentProfile[field]) {
      patch[field] = input[field];
    }
  }
  if (input.fitness_goal !== currentProfile.fitness_goal) {
    patch.fitness_goal = input.fitness_goal;
  }
  if (input.experience_level !== currentProfile.experience_level) {
    patch.experience_level = input.experience_level;
  }
  if (input.training_age_months !== (currentProfile.training_age_months ?? null)) {
    patch.training_age_months = input.training_age_months;
  }
  if (input.training_days_per_week !== currentProfile.training_days_per_week) {
    patch.training_days_per_week = input.training_days_per_week;
  }
  if (input.preferred_weekdays?.join(",") !== currentProfile.preferred_weekdays?.join(",")) {
    patch.preferred_weekdays = input.preferred_weekdays;
  }
  const preservesLegacyMultiplePriorities =
    values.priority_muscle === "" && (currentProfile.priority_muscles?.length ?? 0) > 1;
  if (
    !preservesLegacyMultiplePriorities
    && input.priority_muscles?.join(",") !== currentProfile.priority_muscles?.join(",")
  ) {
    patch.priority_muscles = input.priority_muscles;
  }
  if (input.training_location !== currentProfile.training_location) {
    patch.training_location = input.training_location;
  }
  if (input.home_training_setup !== currentProfile.home_training_setup) {
    patch.home_training_setup = input.home_training_setup;
  }
  const inputEquipmentKey = input.available_equipment?.join(",") ?? "";
  const currentEquipmentKey = normalizeEquipment(currentProfile.available_equipment ?? []).join(",");
  if (inputEquipmentKey !== currentEquipmentKey) {
    patch.available_equipment = input.available_equipment;
  }
  if (input.session_duration_minutes !== currentProfile.session_duration_minutes) {
    patch.session_duration_minutes = input.session_duration_minutes;
  }
  if (input.training_intensity !== currentProfile.training_intensity) {
    patch.training_intensity = input.training_intensity;
  }
  if (input.training_cautions.join(",") !== currentProfile.training_cautions.join(",")) {
    patch.training_cautions = input.training_cautions;
  }
  if (input.plan_duration_weeks !== currentProfile.plan_duration_weeks) {
    patch.plan_duration_weeks = input.plan_duration_weeks;
  }
  return patch;
}

function normalizeEquipment(values: Equipment[]): Equipment[] {
  const selected = new Set(values);
  return availableEquipment.filter((equipment) => selected.has(equipment));
}

function legacySetupEquipment(setup: ProfileFormValues["home_training_setup"]): Equipment[] {
  if (setup === "bodyweight_only") return ["bodyweight", "pull_up_bar"];
  if (setup === "dumbbells_available") return ["bodyweight", "dumbbell"];
  return [];
}

function deriveHomeTrainingSetup(equipment: Equipment[] | null): HomeTrainingSetup | null {
  if (equipment === null) return null;
  const selected = new Set(equipment);
  if (
    selected.has("bodyweight")
    && [...selected].every((item) => item === "bodyweight" || item === "pull_up_bar")
  ) return "bodyweight_only";
  if (equipment.includes("dumbbell")) return "dumbbells_available";
  return null;
}
