export const sexes = ["female", "male", "other", "prefer_not_to_say"] as const;
export type Sex = (typeof sexes)[number];

export const fitnessGoals = [
  "lose_weight",
  "gain_weight",
  "fat_loss",
  "build_muscle",
  "body_recomposition",
  "strength",
] as const;
const legacyFitnessGoals = [
  "improve_fitness",
  "maintain_weight",
] as const;
export type FitnessGoal = (typeof fitnessGoals)[number] | (typeof legacyFitnessGoals)[number];

export const experienceLevels = ["first_month", "beginner", "intermediate", "advanced"] as const;
export type ExperienceLevel = (typeof experienceLevels)[number];

export const trainingIntensities = ["light", "moderate", "vigorous"] as const;
export type TrainingIntensity = (typeof trainingIntensities)[number];

export const trainingLocations = ["home", "gym"] as const;
export type TrainingLocation = (typeof trainingLocations)[number];

export const homeTrainingSetups = ["bodyweight_only", "dumbbells_available"] as const;
export type HomeTrainingSetup = (typeof homeTrainingSetups)[number];

export const availableEquipment = [
  "bodyweight",
  "dumbbell",
  "barbell",
  "cable",
  "machine",
  "resistance_band",
  "bench",
  "pull_up_bar",
] as const;
export type Equipment = (typeof availableEquipment)[number];

export const sessionDurations = [30, 45, 60, 75, 90, 120] as const;
export type SessionDurationMinutes = (typeof sessionDurations)[number];
export const trainingCautions = ["lower_back", "knee", "shoulder", "neck", "wrist", "other"] as const;
export type TrainingCaution = (typeof trainingCautions)[number];

export const preferredWeekdays = [0, 1, 2, 3, 4, 5, 6] as const;
export type PreferredWeekday = (typeof preferredWeekdays)[number];
export const muscleGroups = [
  "chest", "back", "shoulders", "biceps", "triceps", "traps", "forearms", "neck",
  "glutes", "quadriceps", "hamstrings", "adductors", "abductors", "legs", "calves",
  "abs", "obliques", "lower_back",
] as const;
export type MuscleGroup = (typeof muscleGroups)[number];

export const planDurations = [4, 6, 8] as const;
export type PlanDurationWeeks = (typeof planDurations)[number];
export const workoutGenerationMethods = ["fitsho_coach", "ai"] as const;
export type WorkoutGenerationMethod = (typeof workoutGenerationMethods)[number];

export const productModes = ["training", "nutrition", "both"] as const;
export type ProductMode = (typeof productModes)[number];
export type ProfileCompletionState =
  | "product_mode_not_selected"
  | "shared_profile_incomplete"
  | "training_onboarding_incomplete"
  | "medical_review_information_incomplete"
  | "training_ready"
  | "nutrition_onboarding_incomplete"
  | "nutrition_draft_ready"
  | "nutrition_pending_review"
  | "nutrition_ready"
  | "both_ready";

export type ProfileStatusResponse = {
  user_id: string;
  product_mode: ProductMode | null;
  completion_state: ProfileCompletionState;
};

export type SharedProfileInput = Pick<
  ProfileInput,
  "display_name" | "birth_date" | "sex" | "height_cm" | "current_weight_kg" | "fitness_goal"
>;

export type SharedProfile = SharedProfileInput & {
  user_id: string;
  product_mode: ProductMode;
  weight_measured_at: string;
};

export type ProfileInput = {
  display_name: string;
  birth_date: string;
  sex: Sex;
  height_cm: number;
  current_weight_kg: number;
  shoulder_circumference_cm: number | null;
  waist_circumference_cm: number | null;
  hip_circumference_cm: number | null;
  fitness_goal: FitnessGoal;
  experience_level: ExperienceLevel;
  training_age_months?: number | null;
  training_days_per_week: number;
  preferred_weekdays?: number[] | null;
  priority_muscles?: MuscleGroup[] | null;
  training_location: TrainingLocation;
  home_training_setup: HomeTrainingSetup | null;
  available_equipment?: Equipment[] | null;
  session_duration_minutes: SessionDurationMinutes;
  training_intensity?: TrainingIntensity | null;
  physical_limitations: string | null;
  training_cautions: TrainingCaution[];
  plan_duration_weeks: PlanDurationWeeks;
  workout_generation_method?: WorkoutGenerationMethod;
};

export type ProfilePatch = Partial<ProfileInput>;

export type Profile = ProfileInput & {
  user_id: string;
  weight_measured_at: string;
  circumferences_measured_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ProfileFormValues = {
  display_name: string;
  birth_date: string;
  sex: Sex | "";
  height_cm: string;
  current_weight_kg: string;
  shoulder_circumference_cm: string;
  waist_circumference_cm: string;
  hip_circumference_cm: string;
  fitness_goal: FitnessGoal | "";
  experience_level: ExperienceLevel | "";
  training_age_months: string;
  training_days_per_week: string;
  preferred_weekdays: number[];
  priority_muscles: MuscleGroup[];
  training_location: TrainingLocation | "";
  home_training_setup: HomeTrainingSetup | "";
  available_equipment?: Equipment[];
  session_duration_minutes: string;
  training_intensity: TrainingIntensity | "";
  physical_limitations: string;
  training_cautions: TrainingCaution[] | null;
  plan_duration_weeks: string;
};

export type ProfileFormValue =
  | string
  | TrainingCaution[]
  | number[]
  | PreferredWeekday[]
  | MuscleGroup[]
  | Equipment[]
  | null;
