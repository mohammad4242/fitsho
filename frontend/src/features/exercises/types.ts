export const bodyRegions = ["upper_body", "lower_body", "core"] as const;
export type BodyRegion = (typeof bodyRegions)[number];

export const muscleGroups = [
  "chest",
  "back",
  "shoulders",
  "biceps",
  "triceps",
  "traps",
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

export type ExerciseCategories = {
  body_regions: BodyRegionCategory[];
  upper_body: ExerciseCategory[];
  lower_body: ExerciseCategory[];
  core: ExerciseCategory[];
};

export type ExerciseSummary = {
  id: string;
  slug: string;
  name_en: string;
  name_fa: string;
  body_region: BodyRegion;
  primary_muscle: MuscleGroup;
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
  equipment?: Equipment | "";
  difficulty?: Difficulty | "";
  search?: string;
  page?: number;
  page_size?: number;
};
