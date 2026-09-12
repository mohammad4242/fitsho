import {
  toProfileInput,
  validateAll,
  type ProfileValidationErrors,
} from "@fitician/core/profile-validation";
import {
  equipmentForHomeTrainingSetup,
  resolveHomeTrainingSetup,
  type ProductMode,
  type ProfileFormValues,
  type ProfileInput,
  type SharedProfileInput,
} from "@fitician/core/profile";

export const profileFormFields = [
  "display_name",
  "birth_date",
  "sex",
  "height_cm",
  "current_weight_kg",
  "shoulder_circumference_cm",
  "waist_circumference_cm",
  "hip_circumference_cm",
  "fitness_goal",
  "experience_level",
  "training_age_months",
  "training_days_per_week",
  "preferred_weekdays",
  "priority_muscle",
  "training_location",
  "home_training_setup",
  "available_equipment",
  "session_duration_minutes",
  "training_intensity",
  "training_cautions",
  "plan_duration_weeks",
] as const satisfies readonly (keyof ProfileFormValues)[];

export function emptyProfileFormValues(): ProfileFormValues {
  return {
    display_name: "",
    birth_date: "",
    sex: "",
    height_cm: "",
    current_weight_kg: "",
    shoulder_circumference_cm: "",
    waist_circumference_cm: "",
    hip_circumference_cm: "",
    fitness_goal: "",
    experience_level: "",
    training_age_months: "",
    training_days_per_week: "",
    preferred_weekdays: [],
    priority_muscle: "",
    training_location: "",
    home_training_setup: "",
    available_equipment: [],
    session_duration_minutes: "",
    training_intensity: "",
    training_cautions: null,
    plan_duration_weeks: "4",
  };
}

export function sharedProfileInputForFormValues(values: ProfileFormValues): SharedProfileInput {
  return {
    birth_date: values.birth_date.trim(),
    current_weight_kg: Number(values.current_weight_kg.trim()),
    display_name: values.display_name.trim(),
    fitness_goal: values.fitness_goal as SharedProfileInput["fitness_goal"],
    height_cm: Number(values.height_cm.trim()),
    sex: values.sex as SharedProfileInput["sex"],
  };
}

export function profileFormValuesForSharedProfile(
  shared: SharedProfileInput,
): ProfileFormValues {
  const values = emptyProfileFormValues();
  values.birth_date = shared.birth_date;
  values.current_weight_kg = String(shared.current_weight_kg);
  values.display_name = shared.display_name;
  values.fitness_goal = shared.fitness_goal;
  values.height_cm = String(shared.height_cm);
  values.sex = shared.sex;
  return values;
}

export function profileFormValuesForTrainingProfile(input: ProfileInput): ProfileFormValues {
  const values = profileFormValuesForSharedProfile(input);
  values.shoulder_circumference_cm = input.shoulder_circumference_cm === null
    ? ""
    : String(input.shoulder_circumference_cm);
  values.waist_circumference_cm = input.waist_circumference_cm === null
    ? ""
    : String(input.waist_circumference_cm);
  values.hip_circumference_cm = input.hip_circumference_cm === null
    ? ""
    : String(input.hip_circumference_cm);
  values.experience_level = input.experience_level;
  values.training_age_months = input.training_age_months == null
    ? ""
    : String(input.training_age_months);
  values.training_days_per_week = String(input.training_days_per_week);
  values.preferred_weekdays = [...(input.preferred_weekdays ?? [])];
  values.priority_muscle = input.priority_muscles?.length === 1
    ? input.priority_muscles[0]
    : "";
  values.training_location = input.training_location;
  const homeSetup = input.training_location === "home"
    ? resolveHomeTrainingSetup(input.home_training_setup, input.available_equipment)
    : null;
  values.home_training_setup = homeSetup ?? "";
  values.available_equipment = input.training_location === "home"
    ? homeSetup === null ? [] : equipmentForHomeTrainingSetup(homeSetup)
    : input.available_equipment == null ? [] : [...input.available_equipment];
  values.session_duration_minutes = String(input.session_duration_minutes);
  values.training_intensity = input.training_intensity ?? "";
  values.training_cautions = [...input.training_cautions];
  values.plan_duration_weeks = String(input.plan_duration_weeks);
  return values;
}

export function profileInputForOnboarding(
  values: ProfileFormValues,
  today: Date,
): ProfileInput {
  const errors = validateAll(values, today);
  if (Object.keys(errors).length > 0) {
    throw new OnboardingFormValidationError(errors);
  }
  return toProfileInput(values);
}

export class OnboardingFormValidationError extends Error {
  readonly errors: ProfileValidationErrors;

  constructor(errors: ProfileValidationErrors) {
    super("Onboarding profile answers are incomplete");
    this.name = "OnboardingFormValidationError";
    this.errors = errors;
  }
}

export function productModeLabel(mode: ProductMode): string {
  if (mode === "training") return "تمرین";
  if (mode === "nutrition") return "تغذیه";
  return "تمرین و تغذیه";
}
