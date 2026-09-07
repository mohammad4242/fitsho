import { ApiError, formatPrescriptionTarget } from "@fitician/core";

import type {
  WorkoutPlan,
  WorkoutPlanExercise,
  WorkoutPlanVersionSummary,
} from "./workoutApi";
import type { WorkoutCycleCurrent } from "./workoutCycleApi";

export type WorkoutGenerationErrorKind = "cooldown" | "failed" | "in_progress" | "unsupported";
export type WorkoutPlanSummaryStatus = "active" | "pending" | "inactive";

export type WorkoutCycleWeekDisplay = {
  readonly currentWeek: number;
  readonly durationWeeks: number;
  readonly isAtEnd: boolean;
};

export function workoutCycleWeekDisplay(cycle: WorkoutCycleCurrent): WorkoutCycleWeekDisplay {
  return {
    currentWeek: cycle.current_week,
    durationWeeks: cycle.duration_weeks,
    isAtEnd: cycle.current_week >= cycle.duration_weeks,
  };
}

export function classifyWorkoutGenerationError(error: unknown): WorkoutGenerationErrorKind {
  if (!(error instanceof ApiError)) return "failed";
  if (error.status === 429) return "cooldown";
  if (error.status === 409) return "in_progress";
  if (error.status === 422 || error.code !== null) return "unsupported";
  return "failed";
}

export function getWorkoutPlanSummaryStatus(
  plan: WorkoutPlan,
  historical = false,
): WorkoutPlanSummaryStatus {
  if (historical) return "inactive";
  if (plan.status === "pending_review" || plan.coach_review?.state === "pending_coach_review") {
    return "pending";
  }
  return plan.status === "active" ? "active" : "inactive";
}

export function isWorkoutPlanExecutable(plan: WorkoutPlan, historical = false): boolean {
  return !historical
    && plan.status === "active"
    && plan.coach_review?.state !== "pending_coach_review";
}

export function findPendingWorkoutPlanId(
  history: readonly WorkoutPlanVersionSummary[],
): string | null {
  return history.find((version) => version.status === "pending_review")?.id ?? null;
}

export function workoutPlanAverageDuration(plan: WorkoutPlan): number | null {
  if (plan.days.length === 0) return null;
  const total = plan.days.reduce((sum, day) => sum + day.estimated_duration_minutes, 0);
  return Math.round(total / plan.days.length);
}

export function formatWorkoutPrescription(
  exercise: WorkoutPlanExercise,
  language: "fa" | "en" = "fa",
): string {
  return formatPrescriptionTarget(
    exercise as Parameters<typeof formatPrescriptionTarget>[0],
    language,
  );
}

export function workoutPlanPdfFilename(planId: string): string {
  const safeId = planId.replace(/[^A-Za-z0-9_-]/gu, "-").replace(/-+/gu, "-");
  return `fitician-workout-plan-${safeId || "plan"}.pdf`;
}
