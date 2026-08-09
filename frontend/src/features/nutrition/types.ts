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
export type NutritionMicronutrientTarget = {
  reference_kind: string;
  target_value: number;
  unit: string;
  unit_form: string;
  upper_limit_value: number | null;
  upper_limit_kind: string | null;
  upper_limit_scope: string;
  aggregation_window: string;
  policy_version: string;
  source_reference: string;
  applicable_population: string;
  confidence: EstimateConfidence;
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
  micronutrients?: Record<string, NutritionMicronutrientTarget>;
  created_at: string;
};

export type WeeklyPlanNutrient = {
  nutrient_code: string;
  unit: string;
  reference_kind: string | null;
  preferred: number | null;
  minimum_or_maximum: number | null;
  planned: number;
  difference_from_preferred: number | null;
  difference_from_limit: number | null;
  status: string;
  reason_codes: string[];
  data_confidence: string;
  explanation_codes: string[];
};

export type WeeklyPlanFood = {
  food_id: string;
  slug: string;
  name_fa: string;
  name_en: string;
  grams: number;
  cost_irr: number;
  nutrients: Record<string, number>;
};

export type WeeklyPlan = {
  id: string;
  revision: number;
  lifecycle_status: string;
  is_user_visible: boolean;
  physician_approved: boolean;
  review_status: string;
  physician_approved_at: string | null;
  physician_display_name: string | null;
  physician_user_visible_notes: string | null;
  physician_change_summary: Array<Record<string, unknown>>;
  supersedes_plan_id: string | null;
  start_date: string;
  planner_policy_version: string;
  planner_version: string;
  scientific_policy_version: string;
  formula_version: string;
  weekly_cost_irr: number;
  weekly_budget_irr: number;
  budget_status: string;
  warning_codes: string[];
  explanation_codes: string[];
  input_snapshot: Record<string, unknown>;
  price_snapshot: Record<string, unknown>;
  repair_actions: Array<Record<string, unknown>>;
  nutrients: Record<string, WeeklyPlanNutrient>;
  days: Array<{
    day_index: number;
    plan_date: string;
    nutrient_totals: Record<string, number>;
    cost_irr: number;
    meals: Array<{
      id: string;
      slot_role: "main_meal" | "snack";
      slot_index: number;
      target_distribution: Record<string, number>;
      nutrient_totals: Record<string, number>;
      cost_irr: number;
      is_locked: boolean;
      foods: WeeklyPlanFood[];
    }>;
  }>;
  created_at: string;
};

export type WeeklyPlanHistoryItem = Pick<WeeklyPlan, "id" | "revision" | "lifecycle_status" | "review_status" | "weekly_cost_irr" | "weekly_budget_irr" | "budget_status" | "created_at">;

export type ShoppingList = {
  plan_id: string;
  plan_revision: number;
  approval_status: string;
  warning_codes: string[];
  total_cost_irr: number;
  items: Array<{
    food_id: string;
    slug: string;
    name_fa: string;
    name_en: string;
    required_quantity: number;
    canonical_unit: string;
    cost_irr: number;
  }>;
};

export type WeeklyPlanGeneration = {
  generation_id: string;
  outcome:
    | "success"
    | "failed"
    | "safety_blocked"
    | "infeasible"
    | "target_infeasible"
    | "live_price_unavailable";
  reason_codes: string[];
  warning_codes: string[];
  plan: WeeklyPlan | null;
};

export type DailyTrackingSummary = {
  entry_date: string;
  check_in_status: "on_plan" | "mostly_on_plan" | "off_plan" | "not_recorded";
  plan_revision_id: string | null;
  data_status: "sufficient" | "insufficient_data";
  actual_totals: Record<string, number>;
  entries: Array<{
    id: string;
    display_name: string;
    source: string;
    confidence: "high" | "medium" | "low";
    nutrients: Record<string, number>;
    warning_codes: string[];
  }>;
};

export type NutritionAdherence = {
  start: string;
  end: string;
  days: Array<{
    date: string;
    status: "sufficient" | "insufficient_data";
    calorie_adherence: number | null;
    protein_adherence: number | null;
    meal_adherence: number | null;
    tracking_completeness: number;
    exact_entry_ratio: number | null;
    composite_score: number | null;
    formula_version: string;
    planned: Record<string, number>;
    actual: Record<string, number>;
  }>;
  weight_trend: Array<{ measured_at: string; weight_kg: number }>;
  weight_causality_claimed: false;
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
  /** Deprecated compatibility input; current Nutrition flows do not submit it. */
  plan_style?: "economical" | "balanced" | "simple";
  cooking_skill?: "none" | "basic" | "confident";
  maximum_cooking_time_minutes?: number;
  cooking_frequency_per_week?: number;
  meal_preparation_preference?: "daily" | "batch" | "mixed" | "no_cooking";
  refrigerator_access?: boolean;
  freezer_access?: boolean;
  cooking_equipment?: Array<"stove" | "oven" | "microwave" | "air_fryer" | "rice_cooker" | "blender" | "refrigerator">;
  supplied_meals_per_week?: number;
  supplied_meal_source?: string | null;
  foods_available_at_home?: string[];
  never_suggest_foods?: string[];
  refused_foods?: string[];
  preferred_variety?: "low" | "medium" | "high";
  maximum_meal_repetition_per_week?: number;
  accepts_leftovers?: boolean;
  accepts_batch_cooking?: boolean;
  favourite_foods: string[];
  disliked_foods: string[];
  allergies: FoodConstraint[];
  intolerances: FoodConstraint[];
  dietary_pattern: "omnivore" | "vegetarian" | "vegan";
  religious_cultural_exclusions: string[];
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
