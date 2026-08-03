import type { ExerciseSummary } from "../exercises/types";

export type WorkoutPlanStatus = "generating" | "active" | "superseded" | "failed";

export type WorkoutPlanExercise = {
  order_index: number;
  sets: number;
  reps_min: number;
  reps_max: number;
  rest_seconds: number;
  rir: number;
  estimated_minutes: number;
  notes_en: string | null;
  notes_fa: string | null;
  exercise: ExerciseSummary;
  alternatives: WorkoutPlanExerciseAlternative[];
};

export type WorkoutPlanExerciseAlternative = {
  reason_en: string;
  reason_fa: string;
  exercise: ExerciseSummary;
};

export type WorkoutDay = {
  day_number: number;
  title_en: string;
  title_fa: string;
  estimated_duration_minutes: number;
  exercises: WorkoutPlanExercise[];
  ai_coach_explanation_fa?: string | null;
};

export type WorkoutPlan = {
  id: string;
  status: WorkoutPlanStatus;
  created_at: string;
  activated_at: string | null;
  plan_duration_weeks: 4 | 6 | 8;
  is_stale: boolean;
  days: WorkoutDay[];
  body_analysis_provenance?: Record<string, unknown>;
  ai_coach_template_slug?: string | null;
  ai_coach_program_explanation_fa?: string | null;
};

export type WorkoutPlanGeneration = {
  plan: WorkoutPlan;
  reused: boolean;
};
