import type { ExerciseSummary, PrescriptionMode } from "../exercises/types";

export type WorkoutPlanStatus = "generating" | "pending_review" | "active" | "superseded" | "failed";

export type WorkoutPlanExercise = {
  id: string;
  order_index: number;
  sets: number;
  prescription_mode?: PrescriptionMode;
  reps_min: number | null;
  reps_max: number | null;
  duration_min_seconds?: number | null;
  duration_max_seconds?: number | null;
  rest_seconds: number;
  rir: number | null;
  estimated_minutes: number;
  superset_group?: string | null;
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

export type WorkoutCyclePerceivedDifficulty =
  | "too_easy"
  | "easy"
  | "appropriate"
  | "hard"
  | "too_hard";

export type WorkoutCycleRecoveryRating = "good" | "average" | "poor";

export type WorkoutCycleCurrent = {
  cycle_id: string;
  workout_plan_id: string;
  started_at: string;
  duration_weeks: 4 | 6 | 8;
  status: "active" | "completed";
  current_week: number;
};

export type WorkoutCycleWeeklyCheckInPainFollowUp = {
  id: string;
  workout_plan_exercise_id: string;
  note_optional: string | null;
  created_at: string;
};

export type WorkoutCycleWeeklyCheckIn = {
  id: string;
  user_id: string;
  cycle_id: string;
  week_number: number;
  sessions_completed: number;
  perceived_difficulty: WorkoutCyclePerceivedDifficulty;
  recovery_rating: WorkoutCycleRecoveryRating;
  has_pain_or_limitation: boolean;
  pain_follow_up: WorkoutCycleWeeklyCheckInPainFollowUp | null;
  note_optional: string | null;
  submitted_at: string;
  created_at: string;
  updated_at: string;
};

export type WorkoutCycleWeeklyCheckInInput = {
  sessions_completed: number;
  perceived_difficulty: WorkoutCyclePerceivedDifficulty;
  recovery_rating: WorkoutCycleRecoveryRating;
  has_pain_or_limitation: boolean;
  pain_follow_up: {
    workout_plan_exercise_id: string;
    note_optional: string | null;
  } | null;
  note_optional: string | null;
};

export type WorkoutCycleCompletionFeedbackInput = {
  overall_difficulty: WorkoutCyclePerceivedDifficulty | null;
  overall_recovery: WorkoutCycleRecoveryRating | null;
  overall_satisfaction: "very_dissatisfied" | "dissatisfied" | "neutral" | "satisfied" | "very_satisfied" | null;
  strength_progress: "declined" | "unchanged" | "improved" | null;
  muscle_progress: "declined" | "unchanged" | "improved" | null;
  endurance_progress: "declined" | "unchanged" | "improved" | null;
  energy_progress: "declined" | "unchanged" | "improved" | null;
  performance_changes: string | null;
  pain_or_limitation_feedback: string | null;
  note_optional: string | null;
};

export type WorkoutCycleCompletionFeedbackContext = {
  cycle_id: string;
  status: "active" | "completed";
  duration_weeks: 4 | 6 | 8;
  current_week: number;
  is_due: boolean;
  feedback_id: string | null;
  feedback: WorkoutCycleCompletionFeedbackInput | null;
  submitted_at: string | null;
};

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
  warnings?: string[];
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
