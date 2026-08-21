import type { WorkoutPlanExercise } from "./types";

export function formatPrescriptionTarget(
  exercise: WorkoutPlanExercise,
  language: "fa" | "en",
): string {
  if (exercise.prescription_mode === "duration") {
    const min = exercise.duration_min_seconds ?? 0;
    const max = exercise.duration_max_seconds ?? min;
    return language === "fa" ? `${min}–${max} ثانیه` : `${min}–${max} seconds`;
  }
  const min = exercise.reps_min ?? 0;
  const max = exercise.reps_max ?? min;
  return language === "fa" ? `${min}–${max} تکرار` : `${min}–${max} reps`;
}
