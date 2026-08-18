import type { ExerciseSummary } from "../exercises/types";

export type WorkoutPlanStatus = "generating" | "pending_review" | "active" | "superseded" | "failed";

export type WorkoutPlanExercise = {
  id: string;
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

export type WorkoutExerciseReplacementReason =
  | "equipment_unavailable"
  | "uncomfortable"
  | "pain_or_discomfort"
  | "temporary_unavailable"
  | "dislike"
  | "other";

export type WorkoutExerciseReplacementScope = "this_time" | "persistent";

export type WorkoutExerciseReplacement = {
  id: string;
  user_id: string;
  cycle_id: string;
  workout_plan_exercise_id: string;
  original_exercise_id: string;
  replacement_exercise_id: string;
  reason: WorkoutExerciseReplacementReason;
  scope: WorkoutExerciseReplacementScope;
  week_number: number;
  created_at: string;
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
  coach_review?: {
    state: "pending_coach_review" | "initial_generated" | "coach_approved" | "none";
    coach_display_name: string | null;
    coach_note: string | null;
    approved_at: string | null;
  };
};

export type WorkoutPlanGeneration = {
  plan: WorkoutPlan;
  reused: boolean;
};

export type WorkoutPlanVersionSummary = {
  id: string;
  status: WorkoutPlanStatus;
  created_at: string;
  activated_at: string | null;
  is_active: boolean;
  coach_review: NonNullable<WorkoutPlan["coach_review"]>;
};
