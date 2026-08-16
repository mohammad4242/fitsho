import { expect, it } from "vitest";

import {
  emptyAdminExerciseForm,
  slugifyExerciseName,
  toAdminExerciseCreate,
  validateAdminExercise,
} from "./validation";

it("suggests an editable lowercase kebab-case slug", () => {
  expect(slugifyExerciseName("  Dumbbell Fly (Incline)  ")).toBe("dumbbell-fly-incline");
});

it("requires bilingual steps and equipment", () => {
  const errors = validateAdminExercise(emptyAdminExerciseForm());

  expect(errors).toMatchObject({
    slug: "required",
    name_en: "required",
    name_fa: "required",
    muscle_focus: "required",
    equipment: "equipmentRequired",
    instructions_en: "instructionCount",
    instructions_fa: "instructionCount",
  });
});

it("allows an exercise without safety notes", () => {
  const form = emptyAdminExerciseForm();
  Object.assign(form, {
    slug: "rename-only",
    name_en: "Renamed Exercise",
    name_fa: "حرکت تغییرنام‌یافته",
    body_region: "upper_body",
    primary_muscle: "chest",
    muscle_focus: "mid_chest",
    equipment: ["bodyweight"],
    instructions_en: ["Brace", "Lower", "Press"],
    instructions_fa: ["منقبض", "پایین", "بالا"],
    safety_notes_en: [],
    safety_notes_fa: [],
  });

  expect(validateAdminExercise(form)).toEqual({});
  expect(toAdminExerciseCreate(form)).toMatchObject({
    safety_notes_en: [],
    safety_notes_fa: [],
  });
});

it("validates body-region membership only for the primary muscle", () => {
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
  });
  expect(validateAdminExercise(form).secondary_muscles).toBeUndefined();
});

it("accepts a cross-region secondary muscle", () => {
  const form = emptyAdminExerciseForm();
  Object.assign(form, {
    slug: "back-row",
    name_en: "Back Row",
    name_fa: "پارویی پشت",
    body_region: "upper_body",
    primary_muscle: "back",
    muscle_focus: "general_back",
    secondary_muscles: ["biceps", "calves"],
    equipment: ["cable"],
    instructions_en: ["Brace", "Pull", "Return"],
    instructions_fa: ["آماده شو", "بکش", "برگرد"],
    safety_notes_en: ["Keep control"],
    safety_notes_fa: ["کنترل را حفظ کن"],
  });

  expect(validateAdminExercise(form)).toEqual({});
});

it("accepts a complete valid bilingual exercise", () => {
  const form = emptyAdminExerciseForm();
  Object.assign(form, {
    slug: "incline-push-up",
    name_en: "Incline Push Up",
    name_fa: "شنا سوئدی شیب‌دار",
    body_region: "upper_body",
    primary_muscle: "chest",
    muscle_focus: "mid_chest",
    secondary_muscles: ["shoulders", "triceps"],
    equipment: ["bodyweight", "bench"],
    instructions_en: ["Brace", "Lower", "Press"],
    instructions_fa: ["منقبض", "پایین", "بالا"],
    safety_notes_en: ["Keep aligned"],
    safety_notes_fa: ["هم‌راستا بمانید"],
  });

  expect(validateAdminExercise(form)).toEqual({});
});

it("requires a focus compatible with the primary muscle", () => {
  const form = emptyAdminExerciseForm();
  Object.assign(form, {
    slug: "incline-push-up",
    name_en: "Incline Push Up",
    name_fa: "شنا سوئدی شیب‌دار",
    body_region: "upper_body",
    primary_muscle: "chest",
    muscle_focus: "front_delt",
    equipment: ["bodyweight"],
    instructions_en: ["Brace", "Lower", "Press"],
    instructions_fa: ["منقبض", "پایین", "بالا"],
    safety_notes_en: ["Keep aligned"],
    safety_notes_fa: ["هم‌راستا بمانید"],
  });

  expect(validateAdminExercise(form)).toMatchObject({ muscle_focus: "muscleFocus" });
});

it("accepts a quadriceps exercise without a focus subcategory", () => {
  const form = emptyAdminExerciseForm();
  Object.assign(form, {
    slug: "leg-extension",
    name_en: "Leg Extension",
    name_fa: "جلو پا دستگاه",
    body_region: "lower_body",
    primary_muscle: "quadriceps",
    muscle_focus: "",
    equipment: ["machine"],
    instructions_en: ["Set up", "Extend", "Lower"],
    instructions_fa: ["تنظیم", "باز کن", "پایین بیاور"],
    safety_notes_en: ["Keep control"],
    safety_notes_fa: ["کنترل را حفظ کن"],
  });

  expect(validateAdminExercise(form)).toEqual({});
  expect(toAdminExerciseCreate(form).muscle_focus).toBeNull();
});

it("accepts lower back as an upper-body muscle group", () => {
  const form = emptyAdminExerciseForm();
  Object.assign(form, {
    slug: "back-extension",
    name_en: "Back Extension",
    name_fa: "باز کردن پشت",
    body_region: "upper_body",
    primary_muscle: "lower_back",
    muscle_focus: "lumbar_erectors",
    equipment: ["bodyweight"],
    instructions_en: ["Set up", "Move", "Return"],
    instructions_fa: ["تنظیم", "حرکت", "برگشت"],
    safety_notes_en: ["Keep control"],
    safety_notes_fa: ["کنترل را حفظ کن"],
  });

  expect(validateAdminExercise(form)).toEqual({});
});

it.each([
  ["abductors", "بیرون پا"],
  ["legs", "کل پا"],
])("accepts a %s exercise without a focus subcategory", (primary_muscle) => {
  const form = emptyAdminExerciseForm();
  Object.assign(form, {
    slug: `${primary_muscle}-exercise`,
    name_en: "Leg Exercise",
    name_fa: "حرکت پا",
    body_region: "lower_body",
    primary_muscle,
    muscle_focus: "",
    equipment: ["bodyweight"],
    instructions_en: ["Set up", "Move", "Return"],
    instructions_fa: ["تنظیم", "حرکت", "برگشت"],
    safety_notes_en: ["Keep control"],
    safety_notes_fa: ["کنترل را حفظ کن"],
  });

  expect(validateAdminExercise(form)).toEqual({});
});

it("allows a review record with labels and no anatomy", () => {
  const form = emptyAdminExerciseForm();
  Object.assign(form, {
    slug: "review-cardio",
    name_en: "Review cardio",
    name_fa: "هوازی بازبینی",
    labels: ["cardio"],
    needs_review: true,
    equipment: ["bodyweight"],
    instructions_en: ["One", "Two", "Three"],
    instructions_fa: ["یک", "دو", "سه"],
    safety_notes_en: ["Keep control"],
    safety_notes_fa: ["کنترل را حفظ کن"],
  });

  expect(validateAdminExercise(form)).toEqual({});
  expect(toAdminExerciseCreate(form)).toMatchObject({
    body_region: null,
    primary_muscle: null,
    muscle_focus: null,
    labels: ["cardio"],
    needs_review: true,
  });
});
