import type { MuscleGroup } from "../exercises/types";
import type { AdminExercise } from "./types";

export type TrainingTemplateExerciseSelection = {
  exercise_id: string;
  exercise_name_fa: string;
  exercise_name_en: string;
  exercise_slug: string;
  movement_pattern: AdminExercise["movement_pattern"];
  target_muscles: MuscleGroup[];
};

export function mapExerciseLibraryToTemplateFields(
  exercise: AdminExercise,
): TrainingTemplateExerciseSelection {
  const muscles = exercise.primary_muscle === null
    ? exercise.secondary_muscles.slice(0, 1)
    : [exercise.primary_muscle, ...exercise.secondary_muscles];

  return {
    exercise_id: exercise.id,
    exercise_name_fa: exercise.name_fa,
    exercise_name_en: exercise.name_en,
    exercise_slug: exercise.slug,
    movement_pattern: exercise.movement_pattern,
    target_muscles: muscles.length > 0 ? muscles : ["chest"],
  };
}
