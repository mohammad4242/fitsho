import { expect, it } from "vitest";

import {
  completionFeedbackFormFromResponse,
  emptyCompletionFeedbackForm,
  emptyWeeklyCheckInForm,
  toCompletionFeedbackInput,
  toWeeklyCheckInInput,
  weeklyCheckInFormFromResponse,
} from "./workoutCycleModel";

it("maps a saved weekly check-in into an editable native form", () => {
  expect(weeklyCheckInFormFromResponse({
    cycle_id: "cycle-1",
    created_at: "2026-09-01T00:00:00Z",
    has_pain_or_limitation: true,
    id: "check-in-1",
    note_optional: null,
    pain_follow_up: {
      created_at: "2026-09-01T00:00:00Z",
      id: "pain-1",
      note_optional: "زانو",
      workout_plan_exercise_id: "exercise-1",
    },
    perceived_difficulty: "hard",
    recovery_rating: "average",
    sessions_completed: 3,
    submitted_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    user_id: "member-1",
    week_number: 2,
  })).toEqual({
    affectedExerciseId: "exercise-1",
    hasPainOrLimitation: true,
    painNote: "زانو",
    perceivedDifficulty: "hard",
    recoveryRating: "average",
    sessionsCompleted: 3,
  });
  expect(weeklyCheckInFormFromResponse(null)).toEqual(emptyWeeklyCheckInForm);
});

it("builds the exact weekly check-in request and clears irrelevant pain data", () => {
  expect(toWeeklyCheckInInput({
    affectedExerciseId: "exercise-1",
    hasPainOrLimitation: false,
    painNote: "ignored",
    perceivedDifficulty: "appropriate",
    recoveryRating: "good",
    sessionsCompleted: 2,
  })).toEqual({
    has_pain_or_limitation: false,
    note_optional: null,
    pain_follow_up: null,
    perceived_difficulty: "appropriate",
    recovery_rating: "good",
    sessions_completed: 2,
  });
});

it("maps end-cycle feedback defaults and preserves submitted values", () => {
  expect(completionFeedbackFormFromResponse(null)).toEqual(emptyCompletionFeedbackForm);
  const form = {
    ...emptyCompletionFeedbackForm,
    overallSatisfaction: "satisfied" as const,
    performanceChanges: "قدرت بیشتر شد",
  };
  expect(toCompletionFeedbackInput(form)).toEqual({
    energy_progress: "unchanged",
    endurance_progress: "unchanged",
    muscle_progress: "unchanged",
    note_optional: null,
    overall_difficulty: "appropriate",
    overall_recovery: "good",
    overall_satisfaction: "satisfied",
    pain_or_limitation_feedback: null,
    performance_changes: "قدرت بیشتر شد",
    strength_progress: "unchanged",
  });
});
