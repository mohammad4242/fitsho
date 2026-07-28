import { expect, it } from "vitest";

import { emptyAdminExerciseForm, slugifyExerciseName, validateAdminExercise } from "./validation";

it("suggests an editable lowercase kebab-case slug", () => {
  expect(slugifyExerciseName("  Dumbbell Fly (Incline)  ")).toBe("dumbbell-fly-incline");
});

it("requires bilingual steps, safety notes, and equipment", () => {
  const errors = validateAdminExercise(emptyAdminExerciseForm());

  expect(errors).toMatchObject({
    slug: "required",
    name_en: "required",
    name_fa: "required",
    equipment: "equipmentRequired",
    instructions_en: "instructionCount",
    instructions_fa: "instructionCount",
    safety_notes_en: "safetyRequired",
    safety_notes_fa: "safetyRequired",
  });
});

it("validates slug format and body-region muscle membership", () => {
  const form = emptyAdminExerciseForm();
  form.slug = "Bad Slug";
  form.name_en = "Test Exercise";
  form.name_fa = "حرکت آزمایشی";
  form.body_region = "upper_body";
  form.primary_muscle = "quadriceps";
  form.secondary_muscles = ["triceps", "calves"];
  form.equipment = ["bodyweight"];
  form.instructions_en = ["One", "Two", "Three"];
  form.instructions_fa = ["یک", "دو", "سه"];
  form.safety_notes_en = ["Safe"];
  form.safety_notes_fa = ["ایمن"];

  expect(validateAdminExercise(form)).toMatchObject({
    slug: "slugFormat",
    primary_muscle: "muscleRegion",
    secondary_muscles: "muscleRegion",
  });
});

it("accepts a complete valid bilingual exercise", () => {
  const form = emptyAdminExerciseForm();
  Object.assign(form, {
    slug: "incline-push-up",
    name_en: "Incline Push Up",
    name_fa: "شنا سوئدی شیب‌دار",
    body_region: "upper_body",
    primary_muscle: "chest",
    secondary_muscles: ["shoulders", "triceps"],
    equipment: ["bodyweight", "bench"],
    instructions_en: ["Brace", "Lower", "Press"],
    instructions_fa: ["منقبض", "پایین", "بالا"],
    safety_notes_en: ["Keep aligned"],
    safety_notes_fa: ["هم‌راستا بمانید"],
  });

  expect(validateAdminExercise(form)).toEqual({});
});
