export const sexes = ["female", "male", "other", "prefer_not_to_say"] as const;
export type Sex = (typeof sexes)[number];

export const fitnessGoals = [
  "lose_weight",
  "build_muscle",
  "improve_fitness",
  "maintain_weight",
] as const;
export type FitnessGoal = (typeof fitnessGoals)[number];

export const experienceLevels = ["beginner", "intermediate", "advanced"] as const;
export type ExperienceLevel = (typeof experienceLevels)[number];

export const trainingLocations = ["home", "gym"] as const;
export type TrainingLocation = (typeof trainingLocations)[number];

export const homeTrainingSetups = ["bodyweight_only", "dumbbells_available"] as const;
export type HomeTrainingSetup = (typeof homeTrainingSetups)[number];

export const sessionDurations = [30, 45, 60, 75, 90] as const;
export type SessionDurationMinutes = (typeof sessionDurations)[number];
export const trainingCautions = ["lower_back", "knee", "shoulder", "neck", "wrist", "other"] as const;
export type TrainingCaution = (typeof trainingCautions)[number];

export const planDurations = [4, 6, 8] as const;
export type PlanDurationWeeks = (typeof planDurations)[number];
export const workoutGenerationMethods = ["fitsho_coach", "ai"] as const;
export type WorkoutGenerationMethod = (typeof workoutGenerationMethods)[number];

export type ProfileInput = {
  display_name: string;
  birth_date: string;
  sex: Sex;
  height_cm: number;
  current_weight_kg: number;
  fitness_goal: FitnessGoal;
  experience_level: ExperienceLevel;
  training_days_per_week: number;
  training_location: TrainingLocation;
  home_training_setup: HomeTrainingSetup | null;
  session_duration_minutes: SessionDurationMinutes;
  physical_limitations: string | null;
  training_cautions: TrainingCaution[];
  plan_duration_weeks: PlanDurationWeeks;
  workout_generation_method?: WorkoutGenerationMethod;
};

export type ProfilePatch = Partial<ProfileInput>;

export type Profile = ProfileInput & {
  user_id: string;
  weight_measured_at: string;
  created_at: string;
  updated_at: string;
};

export type ProfileFormValues = {
  display_name: string;
  birth_date: string;
  sex: Sex | "";
  height_cm: string;
  current_weight_kg: string;
  fitness_goal: FitnessGoal | "";
  experience_level: ExperienceLevel | "";
  training_days_per_week: string;
  training_location: TrainingLocation | "";
  home_training_setup: HomeTrainingSetup | "";
  session_duration_minutes: string;
  physical_limitations: string;
  training_cautions: TrainingCaution[] | null;
  plan_duration_weeks: string;
};
