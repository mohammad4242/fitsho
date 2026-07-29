import type {
  BodyRegion,
  Difficulty,
  Equipment,
  ExerciseCautionTag,
  ExerciseDetail,
  ExerciseType,
  MediaPresentation,
  MediaRole,
  MovementPattern,
  MuscleGroup,
} from "../exercises/types";

export type AdminExerciseMediaAssetInput = {
  presentation: MediaPresentation;
  role: MediaRole;
  media_source_url: string | null;
  media_license: string | null;
  media_attribution: string | null;
};

export type MediaAssetKey = "male_video" | "female_video" | "male_thumbnail" | "female_thumbnail";
export type AdminExerciseMediaFiles = Partial<Record<MediaAssetKey, File>>;

export type AdminExercise = ExerciseDetail & {
  movement_pattern: MovementPattern;
  exercise_type: ExerciseType;
  caution_tags: ExerciseCautionTag[];
  is_programmable: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type AdminExerciseCreate = {
  slug: string;
  name_en: string;
  name_fa: string;
  body_region: BodyRegion;
  primary_muscle: MuscleGroup;
  secondary_muscles: MuscleGroup[];
  equipment: Equipment[];
  difficulty: Difficulty;
  movement_pattern: MovementPattern;
  exercise_type: ExerciseType;
  caution_tags: ExerciseCautionTag[];
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
