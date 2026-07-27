import type {
  ExperienceLevel,
  FitnessGoal,
  Profile,
  ProfileFormValues,
  ProfileInput,
  ProfilePatch,
  Sex,
} from "./types";

export type ProfileValidationCode =
  | "required"
  | "displayNameLength"
  | "birthDateInvalid"
  | "ageRange"
  | "heightRange"
  | "weightRange"
  | "weightPrecision"
  | "trainingDaysRange"
  | "limitationsLength";

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
  } else if (!/^\d+$/.test(height) || Number(height) < 100 || Number(height) > 250) {
    errors.height_cm = "heightRange";
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
    } else if (numericWeight < 20 || numericWeight > 500) {
      errors.current_weight_kg = "weightRange";
    }
  }
  return errors;
}

function validateStepThree(values: ProfileFormValues): ProfileValidationErrors {
  const errors: ProfileValidationErrors = {};
  if (values.fitness_goal === "") {
    errors.fitness_goal = "required";
  }
  if (values.experience_level === "") {
    errors.experience_level = "required";
  }

  const trainingDays = values.training_days_per_week.trim();
  if (trainingDays === "") {
    errors.training_days_per_week = "required";
  } else if (
    !/^\d+$/.test(trainingDays) ||
    Number(trainingDays) < 1 ||
    Number(trainingDays) > 7
  ) {
    errors.training_days_per_week = "trainingDaysRange";
  }

  if (values.physical_limitations.trim().length > 1000) {
    errors.physical_limitations = "limitationsLength";
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
  return {
    display_name: values.display_name.trim(),
    birth_date: values.birth_date.trim(),
    sex: values.sex as Sex,
    height_cm: Number(values.height_cm.trim()),
    current_weight_kg: Number(values.current_weight_kg.trim()),
    fitness_goal: values.fitness_goal as FitnessGoal,
    experience_level: values.experience_level as ExperienceLevel,
    training_days_per_week: Number(values.training_days_per_week.trim()),
    physical_limitations: values.physical_limitations.trim() || null,
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
  if (input.fitness_goal !== currentProfile.fitness_goal) {
    patch.fitness_goal = input.fitness_goal;
  }
  if (input.experience_level !== currentProfile.experience_level) {
    patch.experience_level = input.experience_level;
  }
  if (input.training_days_per_week !== currentProfile.training_days_per_week) {
    patch.training_days_per_week = input.training_days_per_week;
  }
  if (input.physical_limitations !== currentProfile.physical_limitations) {
    patch.physical_limitations = input.physical_limitations;
  }
  return patch;
}
