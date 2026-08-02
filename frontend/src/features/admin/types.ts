import type {
  BodyRegion,
  Difficulty,
  Equipment,
  ExerciseCautionTag,
  ExerciseDetail,
  ExerciseLabel,
  ExerciseType,
  MediaPresentation,
  MediaRole,
  MovementPattern,
  MuscleGroup,
} from "../exercises/types";
import type { ExperienceLevel, FitnessGoal } from "../profile/types";

export type AdminExerciseMediaAssetInput = {
  id?: string | null;
  presentation: MediaPresentation;
  role: MediaRole;
  sort_order: number;
  upload_index?: number | null;
  media_source_url: string | null;
  media_license: string | null;
  media_attribution: string | null;
};

export type AdminExerciseMediaFiles = File[];

export type AdminExercise = ExerciseDetail & {
  movement_pattern: MovementPattern;
  exercise_type: ExerciseType;
  caution_tags: ExerciseCautionTag[];
  labels: ExerciseLabel[];
  needs_review: boolean;
  is_programmable: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type AdminExerciseCreate = {
  slug: string;
  name_en: string;
  name_fa: string;
  body_region: BodyRegion | null;
  primary_muscle: MuscleGroup | null;
  secondary_muscles: MuscleGroup[];
  equipment: Equipment[];
  difficulty: Difficulty;
  movement_pattern: MovementPattern;
  exercise_type: ExerciseType;
  caution_tags: ExerciseCautionTag[];
  labels: ExerciseLabel[];
  needs_review: boolean;
  is_programmable: boolean;
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
  "body_region" | "primary_muscle" | "media_assets"
> & {
  body_region: BodyRegion | "";
  primary_muscle: MuscleGroup | "";
  media_assets: AdminExerciseMediaAssetInput[];
};

export type AdminExerciseFilters = {
  is_active?: boolean | "";
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
  code: string;
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

export type TrainingTemplateMethod = "standard" | "superset" | "drop_set";

export type AdminTrainingTemplateExercise = {
  id: string;
  slug: string;
  name_en: string;
  name_fa: string;
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
  sets: number;
  rep_min: number;
  rep_max: number;
  target_rir: number;
  rest_seconds: number;
  exercise: AdminTrainingTemplateExercise | null;
};

export type AdminTrainingTemplateDay = {
  id: string;
  day_number: number;
  title_en: string;
  title_fa: string;
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
  training_level: ExperienceLevel;
  fitness_goal: FitnessGoal;
  focus_tags: string[];
  intensity_methods: TrainingTemplateMethod[];
  programming_rationale: AdminTrainingTemplateProgrammingRationale[];
  source_name: string;
  source_url: string;
  days: AdminTrainingTemplateDay[];
};

export type AdminTrainingProgramTemplatesResponse = {
  items: AdminTrainingProgramTemplate[];
};
