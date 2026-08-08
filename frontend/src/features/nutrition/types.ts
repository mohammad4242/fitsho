export type MedicalConditionCode =
  | "controlled_hypertension"
  | "lipid_disorder"
  | "type_2_diabetes_non_insulin"
  | "stable_gastrointestinal"
  | "kidney_disease"
  | "dialysis"
  | "liver_disease"
  | "insulin_treated_diabetes"
  | "other";

export type SafetyOutcome =
  | "standard_automatic"
  | "automatic_draft_requires_physician_review"
  | "physician_manual_plan_required"
  | "unsupported_or_hard_blocked";

export type SafetyProfileInput = {
  conditions: Array<{ code: MedicalConditionCode; details: string | null }>;
  medications: Array<{ name: string; dosage: string | null; notes: string | null }>;
  dangerous_food_reaction_history: boolean;
  pregnant: boolean;
  breastfeeding: boolean;
  eating_disorder_diagnosed: boolean;
  eating_disorder_active_symptoms: boolean;
  emergency_or_danger_symptoms: boolean;
  complex_medication_food_interaction: boolean;
  physician_dietary_restrictions: string | null;
  other_relevant_condition: string | null;
};

export type SafetyDecision = {
  id: string;
  outcome: SafetyOutcome;
  policy_version: string;
  reason_codes: string[];
  requires_physician_review: boolean;
  can_continue_onboarding: boolean;
  message: string;
  created_at: string;
};

export type SafetyEvaluation = Omit<SafetyDecision, "id" | "created_at">;

export type FoodConstraint = { name: string; details: string | null };

export type TrainingIntensity = "light" | "moderate" | "vigorous";
export type StructuredExerciseType = "resistance" | "endurance" | "mixed" | "other";
export type StructuredExerciseInput =
  | { trains: false }
  | {
      trains: true;
      exercise_type: StructuredExerciseType;
      days_per_week: number;
      minutes_per_session: number;
      intensity: TrainingIntensity;
    };

export type StructuredExercise = {
  trains: boolean;
  exercise_type: StructuredExerciseType | null;
  days_per_week: number | null;
  minutes_per_session: number | null;
  intensity: TrainingIntensity | null;
  source: "user_reported" | "training_profile" | "active_fitsho_plan";
};

export type EstimateConfidence = "high" | "medium" | "low";
export type NutritionTarget = {
  unit: string;
  minimum: number | null;
  preferred: number | null;
  preferred_maximum: number | null;
  maximum: number | null;
  confidence: EstimateConfidence;
  source_ids: string[];
  explanation_codes: string[];
};

export type NutritionEstimate = {
  id: string;
  revision: number;
  status: "active" | "review_required";
  policy_version: string;
  formula_version: string;
  confidence: EstimateConfidence;
  confidence_reasons: string[];
  is_stale: boolean;
  targets: Record<string, NutritionTarget>;
  created_at: string;
};

export type NutritionProfileInput = {
  daily_activity_level: "sedentary" | "light" | "moderate" | "very_active";
  metabolic_basis?: "female_coefficient" | "male_coefficient" | null;
  individual_monthly_food_budget_irr: number;
  budget_style: "strict" | "flexible";
  main_meal_count_bucket?: "two_main_meals" | "three_main_meals" | "four_or_more_main_meals";
  snack_count_bucket?: "zero_snacks" | "one_snack" | "two_snacks" | "three_or_more_snacks";
  meals_per_day: number;
  snacks_per_day: number;
  preferred_plan_start_day: "saturday" | "sunday" | "monday" | "tuesday" | "wednesday" | "thursday" | "friday";
  plan_style: "economical" | "balanced" | "simple";
  cooking_skill: "none" | "basic" | "confident";
  maximum_cooking_time_minutes: number;
  cooking_frequency_per_week: number;
  meal_preparation_preference: "daily" | "batch" | "mixed" | "no_cooking";
  refrigerator_access: boolean;
  freezer_access: boolean;
  cooking_equipment: Array<"stove" | "oven" | "microwave" | "air_fryer" | "rice_cooker" | "blender" | "refrigerator">;
  supplied_meals_per_week: number;
  supplied_meal_source: string | null;
  foods_available_at_home: string[];
  favourite_foods: string[];
  disliked_foods: string[];
  never_suggest_foods: string[];
  refused_foods: string[];
  allergies: FoodConstraint[];
  intolerances: FoodConstraint[];
  dietary_pattern: "omnivore" | "vegetarian" | "vegan";
  religious_cultural_exclusions: string[];
  preferred_variety: "low" | "medium" | "high";
  maximum_meal_repetition_per_week: number;
  accepts_leftovers: boolean;
  accepts_batch_cooking: boolean;
  work_shift_context: string | null;
  daily_check_in_enabled: boolean;
  preferred_check_in_time: string | null;
};

export type NutritionProfile = NutritionProfileInput & {
  user_id: string;
  onboarding_status: "in_progress" | "completed";
  currency: "IRR";
  weekly_budget_irr: number;
  effective_main_meal_slots?: number;
  effective_snack_slots?: number;
  physician_review_required: boolean;
  created_at: string;
  updated_at: string;
};
