import type {
  BodyRegion,
  Difficulty,
  Equipment,
  ExerciseDetail,
  MuscleGroup,
} from "../exercises/types";

export type AdminExercise = ExerciseDetail & {
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
  instructions_en: string[];
  instructions_fa: string[];
  safety_notes_en: string[];
  safety_notes_fa: string[];
  media_source_url: string | null;
  media_license: string | null;
  media_attribution: string | null;
  is_active: boolean;
};

export type AdminExerciseForm = Omit<
  AdminExerciseCreate,
  "body_region" | "primary_muscle"
> & {
  body_region: BodyRegion | "";
  primary_muscle: MuscleGroup | "";
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
