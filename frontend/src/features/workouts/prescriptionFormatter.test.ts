import { describe, expect, it } from "vitest";

import { formatPrescriptionTarget } from "./prescriptionFormatter";
import type { WorkoutPlanExercise } from "./types";

const baseExercise = {
  id: "exercise-1",
  order_index: 1,
  sets: 2,
  rest_seconds: 60,
  rir: null,
  estimated_minutes: 4,
  notes_en: null,
  notes_fa: null,
  alternatives: [],
  exercise: {} as WorkoutPlanExercise["exercise"],
};

describe("formatPrescriptionTarget", () => {
  it("formats duration prescriptions as seconds", () => {
    const exercise: WorkoutPlanExercise = {
      ...baseExercise,
      prescription_mode: "duration",
      reps_min: null,
      reps_max: null,
      duration_min_seconds: 20,
      duration_max_seconds: 40,
    };

    expect(formatPrescriptionTarget(exercise, "fa")).toBe("20–40 ثانیه");
    expect(formatPrescriptionTarget(exercise, "en")).toBe("20–40 seconds");
  });

  it("keeps repetition prescriptions as reps", () => {
    const exercise: WorkoutPlanExercise = {
      ...baseExercise,
      prescription_mode: "reps",
      reps_min: 8,
      reps_max: 12,
    };

    expect(formatPrescriptionTarget(exercise, "fa")).toBe("8–12 تکرار");
    expect(formatPrescriptionTarget(exercise, "en")).toBe("8–12 reps");
  });
});
