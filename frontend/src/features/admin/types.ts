import type {
  BodyRegion,
  Difficulty,
  Equipment,
  ExerciseCautionTag,
  ExerciseContentType,
  ExerciseDetail,
  ExerciseLabel,
  ExerciseType,
  MediaPresentation,
  MediaRole,
  MediaType,
  MovementPattern,
  MuscleFocus,
  MuscleGroup,
} from "../exercises/types";
import type { ExperienceLevel, FitnessGoal } from "../profile/types";

export type AdminExerciseMediaAssetInput = {
  id?: string | null;
  media_path?: string | null;
  presentation: MediaPresentation;
  role: MediaRole;
  sort_order: number;
  upload_index?: number | null;
  media_source_url: string | null;
  media_license: string | null;
  media_attribution: string | null;
};

export type AdminExerciseMediaFiles = File[];

export const bodyPositions = ["standing", "seated", "lying", "supported"] as const;
export type BodyPosition = (typeof bodyPositions)[number];
export const stabilityDemands = ["low", "moderate", "high"] as const;
export type StabilityDemand = (typeof stabilityDemands)[number];
export const skillDemands = ["low", "moderate", "high"] as const;
export type SkillDemand = (typeof skillDemands)[number];
export const impactLevels = ["low", "moderate", "high"] as const;
export type ImpactLevel = (typeof impactLevels)[number];
export const axialLoadingLevels = ["none", "low", "moderate", "high"] as const;
export type AxialLoadingLevel = (typeof axialLoadingLevels)[number];
export const lateralities = ["bilateral", "unilateral", "not_applicable"] as const;
export type Laterality = (typeof lateralities)[number];

export type AdminExerciseMediaAsset = AdminExerciseMediaAssetInput & {
  id: string;
  media_path: string;
  media_type: MediaType;
};

export type AdminExercise = Omit<ExerciseDetail, "media_assets"> & {
  media_assets?: AdminExerciseMediaAsset[];
  movement_pattern: MovementPattern;
  exercise_type: ExerciseType;
  caution_tags: ExerciseCautionTag[];
  labels: ExerciseLabel[];
  needs_review: boolean;
  is_programmable: boolean;
  body_position: BodyPosition | null;
  stability_demand: StabilityDemand | null;
  skill_demand: SkillDemand | null;
  impact_level: ImpactLevel | null;
  axial_loading_level: AxialLoadingLevel | null;
  fatigue_cost: number | null;
  setup_cost: number | null;
  laterality: Laterality | null;
  substitution_group: string | null;
  range_of_motion_profile: string[] | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type AdminExerciseCreate = {
  slug: string;
  name_en: string;
  name_fa: string;
  content_type: ExerciseContentType;
  body_region: BodyRegion | null;
  primary_muscle: MuscleGroup | null;
  muscle_focus: MuscleFocus | null;
  secondary_muscles: MuscleGroup[];
  equipment: Equipment[];
  difficulty: Difficulty;
  movement_pattern: MovementPattern;
  exercise_type: ExerciseType;
  caution_tags: ExerciseCautionTag[];
  labels: ExerciseLabel[];
  needs_review: boolean;
  is_programmable: boolean;
  body_position: BodyPosition | null;
  stability_demand: StabilityDemand | null;
  skill_demand: SkillDemand | null;
  impact_level: ImpactLevel | null;
  axial_loading_level: AxialLoadingLevel | null;
  fatigue_cost: number | null;
  setup_cost: number | null;
  laterality: Laterality | null;
  substitution_group: string | null;
  range_of_motion_profile: string[] | null;
  instructions_en: string[];
  instructions_fa: string[];
  safety_notes_en: string[];
  safety_notes_fa: string[];
  media_source_url: string | null;
  media_license: string | null;
  media_attribution: string | null;
  media_assets?: AdminExerciseMediaAssetInput[];
  is_active: boolean;
};

export type AdminExerciseForm = Omit<
  AdminExerciseCreate,
  | "body_region"
  | "primary_muscle"
  | "muscle_focus"
  | "body_position"
  | "stability_demand"
  | "skill_demand"
  | "impact_level"
  | "axial_loading_level"
  | "laterality"
  | "substitution_group"
  | "range_of_motion_profile"
  | "media_assets"
> & {
  body_region: BodyRegion | "";
  primary_muscle: MuscleGroup | "";
  muscle_focus: MuscleFocus | "";
  body_position: BodyPosition | "";
  stability_demand: StabilityDemand | "";
  skill_demand: SkillDemand | "";
  impact_level: ImpactLevel | "";
  axial_loading_level: AxialLoadingLevel | "";
  laterality: Laterality | "";
  fatigue_cost: number | null;
  setup_cost: number | null;
  substitution_group: string;
  range_of_motion_profile: string;
  media_assets: AdminExerciseMediaAssetInput[];
};

export type AdminExerciseFilters = {
  content_type?: ExerciseContentType;
  body_region?: BodyRegion | "";
  primary_muscle?: MuscleGroup | "";
  muscle_focus?: MuscleFocus | "";
  equipment?: Equipment | "";
  difficulty?: Difficulty | "";
  exercise_type?: ExerciseType | "";
  labels?: ExerciseLabel[];
  is_active?: boolean | "";
  is_programmable?: boolean | "";
  needs_review?: boolean | "";
  search?: string;
  page?: number;
  page_size?: number;
};

export type PaginatedAdminExercises = {
  items: AdminExercise[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export type ZenApiKind = "responses" | "chat_completions" | "messages" | "gemini";
export type BillingClass = "free" | "paid";
export type RoutingMode = "manual" | "automatic";

export type AdminAiModel = {
  id: string;
  model_id: string;
  display_name: string;
  api_kind: ZenApiKind | null;
  billing_class: BillingClass | null;
  is_enabled: boolean;
  priority: number;
  is_custom: boolean;
  classification_required: boolean;
  last_synced_at: string | null;
  last_checked_at: string | null;
  last_error_code: string | null;
  last_error_message: string | null;
};

export type AdminAiRoutingSettings = {
  mode: RoutingMode;
  manual_model_id: string | null;
};

export type AdminAiModelsResponse = {
  routing: AdminAiRoutingSettings;
  models: AdminAiModel[];
};

export type AdminAiModelUpdate = Partial<Pick<
  AdminAiModel,
  "model_id" | "display_name" | "api_kind" | "billing_class" | "is_enabled" | "priority"
>>;

export type AdminAiModelCreate = {
  model_id: string;
  display_name: string;
  api_kind: ZenApiKind;
  billing_class: BillingClass;
  is_enabled?: boolean;
  priority?: number;
};

export type AdminAiRoutingUpdate = {
  mode: RoutingMode;
  manual_model_id?: string | null;
};

export type AdminAiModelCheck = {
  success: boolean;
  model: AdminAiModel;
  test_run: AdminAiModelTestRun;
};

export type AdminAiModelTestRun = {
  id: string;
  model_id: string;
  outcome: "succeeded" | "failed";
  error_code: string | null;
  safe_error_message: string | null;
  provider_status_code: number | null;
  provider_error_type: string | null;
  provider_error_message: string | null;
  created_at: string;
};

export type AdminAiModelSync = {
  synchronized_model_ids: string[];
  needs_classification: string[];
};

export type AdminAiValidationProblem = {
  code?: string;
  message: string;
  day_number?: number;
  exercise_id?: string;
};

export type AdminAiValidationDiagnostic = {
  model_id: string;
  phase: "initial" | "repair" | "fallback";
  problems: AdminAiValidationProblem[];
};

export type AdminAiGenerationFailure = {
  id: string;
  model_id: string;
  created_at: string;
  completed_at: string | null;
  error_code: string | null;
  safe_error_message: string | null;
  validation_diagnostics: AdminAiValidationDiagnostic[] | null;
};

export type AdminAiTaskType =
  | "workout_plan_generation"
  | "body_photo_analysis"
  | "progress_comparison"
  | "specialist_summary";

export type AdminAiCredentialStatus = {
  configured: boolean;
  masked: string | null;
};

export type AdminAiTaskConfig = {
  task_type: AdminAiTaskType;
  provider: "openrouter";
  enabled: boolean;
  primary_model_id: string | null;
  fallback_model_ids: string[];
  temperature: number;
  max_output_tokens: number;
  timeout_seconds: number;
  minimum_confidence: number;
  max_cost_per_request: string | null;
  routing_restrictions: string[];
  credential: AdminAiCredentialStatus;
  last_successful_connection_test_at: string | null;
  last_model_catalog_refresh_at: string | null;
  last_error_code: string | null;
  last_error_message: string | null;
};

export type AdminAiTaskConfigUpdate = Omit<
  AdminAiTaskConfig,
  | "task_type"
  | "credential"
  | "last_successful_connection_test_at"
  | "last_model_catalog_refresh_at"
  | "last_error_code"
  | "last_error_message"
> & {
  api_key?: string;
  replace_credential: boolean;
};

export type AdminAiCatalogModel = {
  provider: "openrouter";
  model_id: string;
  display_name: string;
  provider_family: string;
  supports_text_input: boolean;
  supports_image_input: boolean;
  supports_structured_output: boolean;
  context_length: number | null;
  input_price_per_token: string | null;
  output_price_per_token: string | null;
  available: boolean;
};

export type AdminAiCatalogResponse = {
  items: AdminAiCatalogModel[];
  refreshed_at: string | null;
  stale: boolean;
};

export type AdminAiProviderTest = {
  ok: boolean;
  checked_at: string;
  model_count: number | null;
  error_code: string | null;
  safe_error_message: string | null;
};

export type AdminAiCatalogRefresh = {
  provider: "openrouter";
  model_count: number;
  refreshed_at: string;
};

export type TrainingTemplateMethod = "standard" | "superset" | "drop_set";
export type TrainingTemplateSlotPriority = "core" | "accessory" | "optional";

export type AdminTrainingTemplateExercise = {
  id: string;
  slug: string;
  name_en: string;
  name_fa: string;
  needs_review: boolean;
};

export type AdminTrainingTemplateSlot = {
  id: string;
  slot_order: number;
  exercise_slug_hint: string;
  placeholder_name_en: string | null;
  placeholder_name_fa: string | null;
  target_muscles: MuscleGroup[];
  movement_pattern: MovementPattern;
  intensity_method: TrainingTemplateMethod;
  adaptation_priority: TrainingTemplateSlotPriority;
  superset_group: string | null;
  superset_exercise_id: string | null;
  sets: number;
  rep_min: number;
  rep_max: number;
  target_rir: number;
  rest_seconds: number;
  exercise: AdminTrainingTemplateExercise | null;
  superset_exercise: AdminTrainingTemplateExercise | null;
};

export type AdminTrainingTemplateDay = {
  id: string;
  day_number: number;
  title_en: string;
  title_fa: string;
  structure_focus: string;
  direct_target_muscles: MuscleGroup[];
  slots: AdminTrainingTemplateSlot[];
};

export type AdminTrainingTemplateProgrammingRationale = {
  title_en: string;
  title_fa: string;
  detail_en: string;
  detail_fa: string;
};

export type AdminTrainingProgramTemplate = {
  id: string;
  slug: string;
  name_en: string;
  name_fa: string;
  description_en: string;
  description_fa: string;
  days_per_week: number;
  supported_levels: ExperienceLevel[];
  focus_tags: string[];
  intensity_methods: TrainingTemplateMethod[];
  programming_rationale: AdminTrainingTemplateProgrammingRationale[];
  source_name: string;
  source_url: string;
  days: AdminTrainingTemplateDay[];
  structure_id: string | null;
};

export type AdminTrainingProgramStructuresResponse = {
  items: AdminTrainingProgramStructure[];
};

export type StructureFamily = "upper_lower" | "split";
export type StructureSplitType = "ppl" | "body_part";

export type AdminTrainingProgramStructureDay = {
  id: string;
  day_number: number;
  label_en: string;
  label_fa: string;
  day_type: string | null;
};

export type AdminTrainingProgramStructure = {
  id: string;
  slug: string;
  name_en: string;
  name_fa: string;
  days_per_week: number;
  family: StructureFamily | null;
  split_type: StructureSplitType | null;
  description_en: string | null;
  description_fa: string | null;
  is_active: boolean;
  structure_days: AdminTrainingProgramStructureDay[];
};

export type AdminTrainingProgramStructureDayWrite = {
  day_number: number;
  label_en: string;
  label_fa: string;
  day_type: string | null;
};

export type AdminTrainingProgramStructureWrite = {
  slug: string;
  name_en: string;
  name_fa: string;
  days_per_week: number;
  family: StructureFamily | null;
  split_type: StructureSplitType | null;
  description_en: string | null;
  description_fa: string | null;
  days: AdminTrainingProgramStructureDayWrite[];
};

export type AdminTrainingProgramTemplatesResponse = {
  items: AdminTrainingProgramTemplate[];
};

export type AdminTrainingTemplateRationaleWrite = {
  title_en: string;
  title_fa: string;
  detail_en: string;
  detail_fa: string;
};

export type AdminTrainingTemplateSlotWrite = {
  exercise_id: string;
  display_name_en: string | null;
  display_name_fa: string | null;
  target_muscles: MuscleGroup[];
  movement_pattern: MovementPattern;
  intensity_method: TrainingTemplateMethod;
  adaptation_priority: TrainingTemplateSlotPriority;
  superset_group: string | null;
  superset_exercise_id: string | null;
  sets: number;
  rep_min: number;
  rep_max: number;
  target_rir: number;
  rest_seconds: number;
};

export type AdminTrainingTemplateDayWrite = {
  title_en: string;
  title_fa: string;
  structure_focus: string;
  direct_target_muscles: MuscleGroup[];
  slots: AdminTrainingTemplateSlotWrite[];
};

export type AdminTrainingProgramTemplateWrite = {
  name_en: string;
  name_fa: string;
  description_en: string;
  description_fa: string;
  days_per_week: number;
  supported_levels: ExperienceLevel[];
  focus_tags: string[];
  intensity_methods: TrainingTemplateMethod[];
  programming_rationale: AdminTrainingTemplateRationaleWrite[];
  source_name: string;
  source_url: string;
  days: AdminTrainingTemplateDayWrite[];
  structure_id: string | null;
};

export type MealCategory = "breakfast" | "lunch" | "post_workout" | "snack" | "dinner";
export type MealVerificationStatus = "draft" | "verified" | "retired";
export type MealIngredientRole =
  | "protein"
  | "carbohydrate"
  | "fat"
  | "fibre"
  | "micronutrient_source";

export type AdminMealIngredient = {
  food_id: string;
  food_slug: string;
  food_name_fa: string;
  food_name_en: string;
  reference_grams: number;
  min_grams: number;
  max_grams: number;
  is_required: boolean;
  functional_role: MealIngredientRole | null;
};

export type PreparedRecipeIngredient = {
  food_id: string;
  food_slug: string;
  food_name_fa: string;
  food_name_en: string;
  reference_grams: number;
  min_grams: number;
  max_grams: number;
  is_required: boolean;
};

export type PreparedRecipeRatio = {
  numerator_food_id: string;
  denominator_food_id: string;
  min_ratio: number;
  max_ratio: number;
};

export type PreparedRecipeDataGap = {
  ingredient_name_fa: string;
  ingredient_name_en: string;
  message_fa: string;
  message_en: string;
};

export type PreparedRecipePreview = {
  final_cooked_yield_grams: number;
  nutrients_per_100g: Record<string, number>;
  estimated_cost_irr_per_100g: number | null;
  price_reference_ids: string[];
};

export type AdminPreparedRecipe = {
  id?: string;
  version?: number;
  verification_status: MealVerificationStatus;
  calculation_version?: string;
  source_name: string;
  source_reference: string;
  notes: string | null;
  cooked_yield: {
    method: "proportional_reference_batch";
    reference_input_grams?: number;
    final_cooked_yield_grams: number;
    source_name: string;
    source_reference: string;
    notes: string | null;
  };
  ingredients: PreparedRecipeIngredient[];
  ratios: PreparedRecipeRatio[];
  data_gaps: PreparedRecipeDataGap[];
  preview?: PreparedRecipePreview;
};

export type AdminPreparedRecipeWrite = Omit<AdminPreparedRecipe, "id" | "version" | "calculation_version" | "preview" | "ingredients"> & {
  ingredients: Array<Pick<PreparedRecipeIngredient, "food_id" | "reference_grams" | "min_grams" | "max_grams" | "is_required">>;
};

export type AdminMealCatalogueItem = {
  id: string;
  code: string;
  name_fa: string;
  name_en: string;
  image_url: string | null;
  category: MealCategory;
  verification_status: MealVerificationStatus;
  calculation_mode?: "simple" | "prepared_recipe";
  items: AdminMealIngredient[];
  prepared_recipe: AdminPreparedRecipe | null;
  totals: Record<string, number | null>;
};

export type AdminMealCatalogueResponse = {
  items: AdminMealCatalogueItem[];
  categories: MealCategory[];
};

export type AdminMealIngredientWrite = Pick<
  AdminMealIngredient,
  | "food_id"
  | "reference_grams"
  | "min_grams"
  | "max_grams"
  | "is_required"
  | "functional_role"
>;

export type AdminMealWrite = {
  code: string;
  name_fa: string;
  name_en: string;
  category: MealCategory;
  verification_status: MealVerificationStatus;
  calculation_mode?: "simple" | "prepared_recipe";
  items: AdminMealIngredientWrite[];
  prepared_recipe?: AdminPreparedRecipeWrite | null;
};

export type NutritionDietStyle =
  | "economy"
  | "balanced_iranian"
  | "high_protein_gym"
  | "quick_easy"
  | "premium_varied";

export type NutritionProgramLifecycle = "active" | "archived" | "all";

export type AdminNutritionProgramMeal = {
  id: string;
  code: string;
  name_fa: string;
  name_en: string;
  image_url: string | null;
  category: MealCategory;
};

export type AdminNutritionProgramSlot = {
  id: string;
  kind?: "catalogue_meal" | "free_meal";
  category: MealCategory;
  meal: AdminNutritionProgramMeal | null;
};

export type AdminNutritionProgramDay = {
  id: string;
  day_number: number;
  post_workout_enabled: boolean;
  slots: AdminNutritionProgramSlot[];
};

export type AdminNutritionProgram = {
  id: string;
  code?: string;
  slug: string;
  name_fa: string;
  name_en: string;
  description_fa: string;
  description_en: string;
  diet_style: NutritionDietStyle;
  post_workout_enabled: boolean;
  is_active: boolean;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
  days: AdminNutritionProgramDay[];
};

export type AdminNutritionProgramPage = {
  items: AdminNutritionProgram[];
  diet_styles: NutritionDietStyle[];
};

export type AdminNutritionProgramSlotWrite = {
  category: MealCategory;
  kind?: "catalogue_meal" | "free_meal";
  meal_id: string | null;
};

export type AdminNutritionProgramDayWrite = {
  day_number: number;
  post_workout_enabled: boolean;
  slots: AdminNutritionProgramSlotWrite[];
};

export type AdminNutritionProgramWrite = {
  code?: string | null;
  name_fa: string;
  name_en: string;
  description_fa: string;
  description_en: string;
  diet_style: NutritionDietStyle;
  post_workout_enabled: boolean;
  days: AdminNutritionProgramDayWrite[];
};
