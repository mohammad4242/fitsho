import { expect, it } from "vitest";

import { formatPrescriptionTarget } from "./formatters";
import type { WorkoutPlanExercise } from "./workouts";

const exercise = {
  prescription_mode: "reps",
  reps_max: 12,
  reps_min: 8,
} as WorkoutPlanExercise;

it("keeps Persian prescription numerals readable without changing English output", () => {
  expect(formatPrescriptionTarget(exercise, "fa")).toBe("۸–۱۲ تکرار");
  expect(formatPrescriptionTarget(exercise, "en")).toBe("8–12 reps");
});
