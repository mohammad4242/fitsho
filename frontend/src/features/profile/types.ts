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

export type ProfileInput = {
  display_name: string;
  birth_date: string;
  sex: Sex;
  height_cm: number;
  current_weight_kg: number;
  fitness_goal: FitnessGoal;
  experience_level: ExperienceLevel;
  training_days_per_week: number;
  physical_limitations: string | null;
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
  physical_limitations: string;
};
