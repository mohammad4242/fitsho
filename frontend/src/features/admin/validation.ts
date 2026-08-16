import {
  muscleFocusesByMuscle,
  type BodyRegion,
  type MuscleGroup,
} from "../exercises/types";
import type { AdminExerciseCreate, AdminExerciseForm } from "./types";

export type AdminValidationCode =
  | "required"
  | "slugFormat"
  | "equipmentRequired"
  | "instructionCount"
  | "muscleRegion"
  | "muscleFocus"
  | "primaryRepeated"
  | "invalidUrl";

export type AdminValidationErrors = Partial<
  Record<keyof AdminExerciseForm, AdminValidationCode>
>;

export const musclesByRegion: Record<BodyRegion, readonly MuscleGroup[]> = {
  upper_body: ["chest", "back", "shoulders", "biceps", "triceps", "traps", "forearms", "neck"],
  lower_body: ["glutes", "quadriceps", "hamstrings", "adductors", "abductors", "legs", "calves"],
  core: ["abs", "obliques"],
};

export function emptyAdminExerciseForm(): AdminExerciseForm {
  return {
    slug: "",
    name_en: "",
    name_fa: "",
    content_type: "exercise",
    body_region: "",
    primary_muscle: "",
    muscle_focus: "",
    secondary_muscles: [],
    equipment: [],
    difficulty: "beginner",
    movement_pattern: "other",
    exercise_type: "other",
    caution_tags: [],
    labels: [],
    needs_review: false,
    is_programmable: false,
    instructions_en: ["", "", ""],
    instructions_fa: ["", "", ""],
    safety_notes_en: [""],
    safety_notes_fa: [""],
    is_active: true,
    media_source_url: null,
    media_license: null,
    media_attribution: null,
    media_assets: [],
  };
}

export function slugifyExerciseName(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 120);
}

function nonEmptyCount(values: string[]): number {
  return values.filter((value) => value.trim().length > 0).length;
}

function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

export function validateAdminExercise(form: AdminExerciseForm): AdminValidationErrors {
  const errors: AdminValidationErrors = {};
  if (!form.slug.trim()) errors.slug = "required";
  else if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(form.slug)) errors.slug = "slugFormat";
  if (!form.name_en.trim()) errors.name_en = "required";
  if (!form.name_fa.trim()) errors.name_fa = "required";
  if (!form.needs_review && !form.body_region) errors.body_region = "required";
  if (!form.needs_review && !form.primary_muscle) errors.primary_muscle = "required";
  if (
    !form.needs_review
    && (
      !form.primary_muscle
      || muscleFocusesByMuscle[form.primary_muscle].length > 0
    )
    && !form.muscle_focus
  ) errors.muscle_focus = "required";
  if (form.needs_review && Boolean(form.body_region) !== Boolean(form.primary_muscle)) {
    errors.primary_muscle = "required";
  }
  if (form.equipment.length === 0) errors.equipment = "equipmentRequired";

  const enSteps = nonEmptyCount(form.instructions_en);
  const faSteps = nonEmptyCount(form.instructions_fa);
  if (enSteps < 3 || enSteps > 6) errors.instructions_en = "instructionCount";
  if (faSteps < 3 || faSteps > 6) errors.instructions_fa = "instructionCount";

  if (form.body_region) {
    const allowed = musclesByRegion[form.body_region];
    if (form.primary_muscle && !allowed.includes(form.primary_muscle)) {
      errors.primary_muscle = "muscleRegion";
    }
  }
  if (form.primary_muscle && form.secondary_muscles.includes(form.primary_muscle)) {
    errors.secondary_muscles = "primaryRepeated";
  }
  if (
    form.primary_muscle
    && form.muscle_focus
    && !muscleFocusesByMuscle[form.primary_muscle].includes(form.muscle_focus)
  ) {
    errors.muscle_focus = "muscleFocus";
  }
  if (form.media_source_url && !isHttpUrl(form.media_source_url)) {
    errors.media_source_url = "invalidUrl";
  }
  return errors;
}

export function toAdminExerciseCreate(form: AdminExerciseForm): AdminExerciseCreate {
  if (
    (
      !form.needs_review
      && (
        !form.body_region
        || !form.primary_muscle
        || (
          muscleFocusesByMuscle[form.primary_muscle].length > 0
          && !form.muscle_focus
        )
      )
    )
    || Boolean(form.body_region) !== Boolean(form.primary_muscle)
  ) {
    throw new Error("Cannot serialize an invalid admin exercise form");
  }
  const trimList = (items: string[]) => items.map((item) => item.trim()).filter(Boolean);
  const optional = (value: string | null) => value?.trim() || null;
  return {
    ...form,
    slug: form.slug.trim(),
    name_en: form.name_en.trim(),
    name_fa: form.name_fa.trim(),
    body_region: form.body_region || null,
    primary_muscle: form.primary_muscle || null,
    muscle_focus: form.muscle_focus || null,
    instructions_en: trimList(form.instructions_en),
    instructions_fa: trimList(form.instructions_fa),
    safety_notes_en: trimList(form.safety_notes_en),
    safety_notes_fa: trimList(form.safety_notes_fa),
    media_source_url: optional(form.media_source_url),
    media_license: optional(form.media_license),
    media_attribution: optional(form.media_attribution),
    media_assets: form.media_assets.map((asset) => ({
      ...asset,
      media_source_url: optional(asset.media_source_url),
      media_license: optional(asset.media_license),
      media_attribution: optional(asset.media_attribution),
    })),
  };
}

export function adminExerciseToForm(exercise: import("./types").AdminExercise): AdminExerciseForm {
  return {
    slug: exercise.slug,
    name_en: exercise.name_en,
    name_fa: exercise.name_fa,
    content_type: exercise.content_type,
    body_region: exercise.body_region ?? "",
    primary_muscle: exercise.primary_muscle ?? "",
    muscle_focus: exercise.muscle_focus ?? "",
    secondary_muscles: exercise.secondary_muscles,
    equipment: exercise.equipment,
    difficulty: exercise.difficulty,
    movement_pattern: exercise.movement_pattern,
    exercise_type: exercise.exercise_type,
    caution_tags: exercise.caution_tags,
    labels: exercise.labels,
    needs_review: exercise.needs_review,
    is_programmable: exercise.is_programmable,
    instructions_en: exercise.instructions_en,
    instructions_fa: exercise.instructions_fa,
    safety_notes_en: exercise.safety_notes_en,
    safety_notes_fa: exercise.safety_notes_fa,
    media_source_url: exercise.media_source_url,
    media_license: exercise.media_license,
    media_attribution: exercise.media_attribution,
    media_assets: exercise.media_assets?.map((asset) => ({
      presentation: asset.presentation,
      role: asset.role,
      sort_order: asset.sort_order,
      upload_index: null,
      media_source_url: asset.media_source_url,
      media_license: asset.media_license,
      media_attribution: asset.media_attribution,
    })) ?? [],
    is_active: exercise.is_active,
  };
}
