export const bodyRegions = ["upper_body", "lower_body", "core"] as const;
export type BodyRegion = (typeof bodyRegions)[number];

export const muscleGroups = [
  "chest",
  "back",
  "shoulders",
  "biceps",
  "triceps",
  "traps",
  "forearms",
  "neck",
  "glutes",
  "quadriceps",
  "hamstrings",
  "adductors",
  "calves",
  "abs",
  "obliques",
  "lower_back",
] as const;
export type MuscleGroup = (typeof muscleGroups)[number];

export const muscleFocuses = [
  "general_chest", "upper_chest", "mid_chest", "lower_chest",
  "general_back", "lats", "mid_back_rhomboids", "upper_back",
  "general_shoulders", "front_delt", "lateral_delt", "rear_delt",
  "general_biceps", "biceps_brachii", "brachialis_brachioradialis",
  "general_triceps", "triceps_long_head", "triceps_lateral_medial_heads",
  "upper_traps", "mid_lower_traps",
  "general_forearms", "forearm_flexors", "forearm_extensors",
  "neck_flexion", "neck_lateral_extension",
  "glute_max", "glute_medius_minimus",
  "general_quadriceps", "rectus_femoris", "vasti",
  "hamstrings_hip_extension", "hamstrings_knee_flexion",
  "hip_adduction", "adductor_mobility",
  "general_calves", "gastrocnemius", "soleus",
  "trunk_flexion", "hip_flexion_posterior_tilt", "anti_extension",
  "trunk_rotation", "lateral_flexion", "anti_rotation",
  "lumbar_erectors", "thoracic_mobility",
] as const;
export type MuscleFocus = (typeof muscleFocuses)[number];

export const muscleFocusesByMuscle: Record<MuscleGroup, readonly MuscleFocus[]> = {
  chest: ["general_chest", "upper_chest", "mid_chest", "lower_chest"],
  back: ["general_back", "lats", "mid_back_rhomboids", "upper_back"],
  shoulders: ["general_shoulders", "front_delt", "lateral_delt", "rear_delt"],
  biceps: ["general_biceps", "biceps_brachii", "brachialis_brachioradialis"],
  triceps: ["general_triceps", "triceps_long_head", "triceps_lateral_medial_heads"],
  traps: ["upper_traps", "mid_lower_traps"],
  forearms: ["general_forearms", "forearm_flexors", "forearm_extensors"],
  neck: ["neck_flexion", "neck_lateral_extension"],
  glutes: ["glute_max", "glute_medius_minimus"],
  quadriceps: [],
  hamstrings: ["hamstrings_hip_extension", "hamstrings_knee_flexion"],
  adductors: ["hip_adduction", "adductor_mobility"],
  calves: ["general_calves", "gastrocnemius", "soleus"],
  abs: ["trunk_flexion", "hip_flexion_posterior_tilt", "anti_extension"],
  obliques: ["trunk_rotation", "lateral_flexion", "anti_rotation"],
  lower_back: ["lumbar_erectors", "thoracic_mobility"],
};

export const equipment = [
  "bodyweight",
  "dumbbell",
  "barbell",
  "cable",
  "machine",
  "resistance_band",
  "bench",
  "pull_up_bar",
  "other",
] as const;
export type Equipment = (typeof equipment)[number];

export const difficulties = ["beginner", "intermediate", "advanced"] as const;
export type Difficulty = (typeof difficulties)[number];

export const movementPatterns = [
  "horizontal_push",
  "vertical_push",
  "horizontal_pull",
  "vertical_pull",
  "squat",
  "hip_hinge",
  "lunge",
  "knee_extension",
  "knee_flexion",
  "hip_extension",
  "hip_abduction",
  "hip_adduction",
  "calf_raise",
  "elbow_flexion",
  "elbow_extension",
  "shoulder_abduction",
  "shoulder_external_rotation",
  "shrug",
  "spinal_flexion",
  "core_anti_extension",
  "core_anti_rotation",
  "core_anti_lateral_flexion",
  "other",
] as const;
export type MovementPattern = (typeof movementPatterns)[number];

export const exerciseTypes = ["compound", "isolation", "core", "mobility", "other"] as const;
export type ExerciseType = (typeof exerciseTypes)[number];

export const exerciseLabels = ["full_body", "cardio"] as const;
export type ExerciseLabel = (typeof exerciseLabels)[number];

export const exerciseCautionTags = [
  "lower_back_loading",
  "spinal_flexion",
  "deep_knee_flexion",
  "overhead_position",
  "shoulder_internal_rotation",
  "shoulder_external_rotation",
  "wrist_loading",
  "neck_loading",
  "balance_demand",
  "other",
] as const;
export type ExerciseCautionTag = (typeof exerciseCautionTags)[number];

export const mediaTypes = [
  "image",
  "animated_webp",
  "gif",
  "video",
  "placeholder",
] as const;
export type MediaType = (typeof mediaTypes)[number];

export const mediaPresentations = ["male", "female"] as const;
export type MediaPresentation = (typeof mediaPresentations)[number];

export const mediaRoles = ["video", "thumbnail"] as const;
export type MediaRole = (typeof mediaRoles)[number];

export type BodyRegionCategory = {
  value: BodyRegion;
  name_en: string;
  name_fa: string;
};

export type ExerciseCategory = {
  value: MuscleGroup;
  name_en: string;
  name_fa: string;
};

export type MuscleFocusCategory = {
  value: MuscleFocus;
  name_en: string;
  name_fa: string;
};

export type ExerciseCategories = {
  body_regions: BodyRegionCategory[];
  upper_body: ExerciseCategory[];
  lower_body: ExerciseCategory[];
  core: ExerciseCategory[];
  muscle_focuses: Record<MuscleGroup, MuscleFocusCategory[]>;
};

export type ExerciseSummary = {
  id: string;
  slug: string;
  name_en: string;
  name_fa: string;
  body_region: BodyRegion | null;
  primary_muscle: MuscleGroup | null;
  muscle_focus: MuscleFocus | null;
  labels: ExerciseLabel[];
  secondary_muscles: MuscleGroup[];
  equipment: Equipment[];
  difficulty: Difficulty;
  media_path: string;
  media_type: MediaType;
};

export type ExerciseDetail = ExerciseSummary & {
  instructions_en: string[];
  instructions_fa: string[];
  safety_notes_en: string[];
  safety_notes_fa: string[];
  media_source_url: string | null;
  media_license: string | null;
  media_attribution: string | null;
  media_assets?: ExerciseMediaAsset[];
};

export type ExerciseMediaAsset = {
  presentation: MediaPresentation;
  role: MediaRole;
  sort_order: number;
  media_path: string;
  media_type: MediaType;
  media_source_url: string | null;
  media_license: string | null;
  media_attribution: string | null;
};

export type PaginatedExercises = {
  items: ExerciseSummary[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export type ExerciseFilters = {
  body_region?: BodyRegion | "";
  primary_muscle?: MuscleGroup | "";
  muscle_focus?: MuscleFocus | "";
  equipment?: Equipment | "";
  difficulty?: Difficulty | "";
  exercise_type?: ExerciseType | "";
  labels?: ExerciseLabel[];
  search?: string;
  page?: number;
  page_size?: number;
};
