import type { PrescriptionMode } from "../exercises/types";
import type { WorkoutPlan } from "../workouts/types";

export type WorkoutReviewStatus = "pending" | "claimed" | "approved" | "superseded";
export type WorkoutReviewQueueView = "pending" | "mine" | "approved";

export type WorkoutReviewExerciseDraft = {
  order_index: number;
  exercise_id: string;
  sets: number;
  prescription_mode?: PrescriptionMode;
  reps_min: number | null;
  reps_max: number | null;
  duration_min_seconds?: number | null;
  duration_max_seconds?: number | null;
  rir: number | null;
  rest_seconds: number;
  notes_en: string | null;
  notes_fa: string | null;
};

export type WorkoutReviewDayDraft = {
  day_number: number;
  exercises: WorkoutReviewExerciseDraft[];
};

export type WorkoutReviewDraftUpdate = {
  expected_revision: number;
  coach_note: string | null;
  days: WorkoutReviewDayDraft[];
};

export type WorkoutReviewQueueItem = {
  id: string;
  source_plan_id: string;
  user_id: string;
  member_display_name: string | null;
  fitness_goal: string | null;
  experience_level: string | null;
  status: WorkoutReviewStatus;
  claimed_by_user_id: string | null;
  lease_expires_at: string | null;
  draft_revision: number;
  created_at: string;
  approved_at: string | null;
};

export type WorkoutReviewDetail = WorkoutReviewQueueItem & {
  coach_note: string | null;
  draft: { days: WorkoutReviewDayDraft[] } | null;
  source_plan: WorkoutPlan;
  exercise_options: Array<{
    id: string;
    name_en: string;
    name_fa: string;
    prescription_mode?: PrescriptionMode;
    duration_min_seconds?: number | null;
    duration_max_seconds?: number | null;
  }>;
};
