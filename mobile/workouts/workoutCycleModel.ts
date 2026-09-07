import type {
  WorkoutCycleCompletionFeedbackInput,
  WorkoutCycleCompletionFeedback,
  WorkoutCycleWeeklyCheckIn,
  WorkoutCycleWeeklyCheckInInput,
} from "./workoutCycleApi";

export type WeeklyCheckInForm = {
  readonly affectedExerciseId: string;
  readonly hasPainOrLimitation: boolean;
  readonly painNote: string;
  readonly perceivedDifficulty: WorkoutCycleWeeklyCheckInInput["perceived_difficulty"];
  readonly recoveryRating: WorkoutCycleWeeklyCheckInInput["recovery_rating"];
  readonly sessionsCompleted: number;
};

export type CompletionFeedbackForm = {
  readonly energyProgress: NonNullable<WorkoutCycleCompletionFeedbackInput["energy_progress"]>;
  readonly enduranceProgress: NonNullable<WorkoutCycleCompletionFeedbackInput["endurance_progress"]>;
  readonly muscleProgress: NonNullable<WorkoutCycleCompletionFeedbackInput["muscle_progress"]>;
  readonly note: string;
  readonly overallDifficulty: NonNullable<WorkoutCycleCompletionFeedbackInput["overall_difficulty"]>;
  readonly overallRecovery: NonNullable<WorkoutCycleCompletionFeedbackInput["overall_recovery"]>;
  readonly overallSatisfaction: NonNullable<WorkoutCycleCompletionFeedbackInput["overall_satisfaction"]>;
  readonly painFeedback: string;
  readonly performanceChanges: string;
  readonly strengthProgress: NonNullable<WorkoutCycleCompletionFeedbackInput["strength_progress"]>;
};

export const emptyWeeklyCheckInForm: WeeklyCheckInForm = {
  affectedExerciseId: "",
  hasPainOrLimitation: false,
  painNote: "",
  perceivedDifficulty: "appropriate",
  recoveryRating: "good",
  sessionsCompleted: 0,
};

export const emptyCompletionFeedbackForm: CompletionFeedbackForm = {
  energyProgress: "unchanged",
  enduranceProgress: "unchanged",
  muscleProgress: "unchanged",
  note: "",
  overallDifficulty: "appropriate",
  overallRecovery: "good",
  overallSatisfaction: "neutral",
  painFeedback: "",
  performanceChanges: "",
  strengthProgress: "unchanged",
};

export function weeklyCheckInFormFromResponse(
  response: WorkoutCycleWeeklyCheckIn | null,
): WeeklyCheckInForm {
  if (response === null) return emptyWeeklyCheckInForm;
  return {
    affectedExerciseId: response.pain_follow_up?.workout_plan_exercise_id ?? "",
    hasPainOrLimitation: response.has_pain_or_limitation,
    painNote: response.pain_follow_up?.note_optional ?? "",
    perceivedDifficulty: response.perceived_difficulty,
    recoveryRating: response.recovery_rating,
    sessionsCompleted: response.sessions_completed,
  };
}

export function toWeeklyCheckInInput(form: WeeklyCheckInForm): WorkoutCycleWeeklyCheckInInput {
  return {
    has_pain_or_limitation: form.hasPainOrLimitation,
    note_optional: null,
    pain_follow_up: form.hasPainOrLimitation
      ? {
        note_optional: form.painNote.trim() || null,
        workout_plan_exercise_id: form.affectedExerciseId,
      }
      : null,
    perceived_difficulty: form.perceivedDifficulty,
    recovery_rating: form.recoveryRating,
    sessions_completed: form.sessionsCompleted,
  };
}

export function completionFeedbackFormFromResponse(
  response: WorkoutCycleCompletionFeedback["feedback"],
): CompletionFeedbackForm {
  if (response === null) return emptyCompletionFeedbackForm;
  return {
    energyProgress: response.energy_progress ?? emptyCompletionFeedbackForm.energyProgress,
    enduranceProgress: response.endurance_progress ?? emptyCompletionFeedbackForm.enduranceProgress,
    muscleProgress: response.muscle_progress ?? emptyCompletionFeedbackForm.muscleProgress,
    note: response.note_optional ?? "",
    overallDifficulty: response.overall_difficulty ?? emptyCompletionFeedbackForm.overallDifficulty,
    overallRecovery: response.overall_recovery ?? emptyCompletionFeedbackForm.overallRecovery,
    overallSatisfaction: response.overall_satisfaction ?? emptyCompletionFeedbackForm.overallSatisfaction,
    painFeedback: response.pain_or_limitation_feedback ?? "",
    performanceChanges: response.performance_changes ?? "",
    strengthProgress: response.strength_progress ?? emptyCompletionFeedbackForm.strengthProgress,
  };
}

export function toCompletionFeedbackInput(form: CompletionFeedbackForm): WorkoutCycleCompletionFeedbackInput {
  return {
    energy_progress: form.energyProgress,
    endurance_progress: form.enduranceProgress,
    muscle_progress: form.muscleProgress,
    note_optional: form.note.trim() || null,
    overall_difficulty: form.overallDifficulty,
    overall_recovery: form.overallRecovery,
    overall_satisfaction: form.overallSatisfaction,
    pain_or_limitation_feedback: form.painFeedback.trim() || null,
    performance_changes: form.performanceChanges.trim() || null,
    strength_progress: form.strengthProgress,
  };
}
