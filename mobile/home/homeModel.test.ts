import { expect, it } from "vitest";

import { currentWorkoutDay, nutritionSummary } from "./homeModel";

const exercise = {
  body_region: "upper_body",
  content_type: "exercise",
  difficulty: "beginner",
  equipment: ["bodyweight"],
  id: "exercise-1",
  media_path: "/media/push-up.gif",
  media_type: "gif",
  muscle_focus: null,
  name_en: "Push-up",
  name_fa: "شنا",
  primary_muscle: "chest",
  secondary_muscles: [],
  slug: "push-up",
} as const;

it("selects the first real workout day without changing plan data", () => {
  const day = currentWorkoutDay({
    days: [{
      ai_coach_explanation_fa: null,
      day_number: 2,
      estimated_duration_minutes: 45,
      exercises: [{
        alternatives: [],
        duration_max_seconds: null,
        duration_min_seconds: null,
        estimated_minutes: 8,
        exercise,
        id: "plan-exercise-1",
        load_guidance: "وزن بدن",
        notes_en: null,
        notes_fa: null,
        order_index: 1,
        prescription_mode: "reps",
        progression_rule: "legacy",
        reps_max: 12,
        reps_min: 8,
        rest_seconds: 60,
        rir: 2,
        section: "main",
        sets: 3,
        superset_group: null,
        warmup_sets: 0,
      }],
      focus: "upper_body",
      main_exercise_count: 1,
      supplemental_exercise_count: 0,
      title_en: "Upper body",
      title_fa: "بالاتنه",
      total_exercise_count: 1,
      weekday: null,
    }],
  } as never);

  expect(day?.day_number).toBe(2);
  expect(day?.exercises[0]?.exercise.media_path).toBe("/media/push-up.gif");
});

it("prefers daily plan totals and calculates progress from target versus TDEE", () => {
  const summary = nutritionSummary(
    {
      days: [{
        day_index: 0,
        meals: [],
        nutrient_totals: {
          energy_kcal: 2200,
          protein_g: 150,
          carbohydrate_g: 240,
          total_fat_g: 70,
        },
        plan_date: "2026-09-09",
      }],
      physician_approved: true,
    } as never,
    {
      targets: {
        goal_calories: { preferred: 2300, minimum: 2000 },
        tdee: { preferred: 2557, minimum: 2400 },
        protein: { preferred: 145, minimum: 120 },
        carbohydrate: { preferred: 240, minimum: 200 },
        total_fat: { preferred: 70, minimum: 50 },
      },
    } as never,
    {
      actual_totals: { energy_kcal: 880, protein_g: 64, carbohydrate_g: 90, total_fat_g: 22 },
      check_in_status: "on_plan",
      data_status: "sufficient",
      entries: [{ id: "entry-1" }],
    } as never,
    "2026-09-09",
  );

  expect(summary.targetCalories).toBe(2200);
  expect(summary.estimatedDailyExpenditureCalories).toBe(2557);
  expect(summary.consumedCalories).toBe(880);
  expect(summary.progress).toBeCloseTo(2200 / 2557);
  expect(summary.protein).toBe(64);
  expect(summary.carbohydrate).toBe(90);
  expect(summary.fat).toBe(22);
  expect(summary.status).toBe("on_plan");
});

it("uses estimate metric names when the daily plan has no nutrient totals", () => {
  const summary = nutritionSummary(
    { days: [], physician_approved: true } as never,
    {
      targets: {
        goal_calories: { preferred: 2778, minimum: 2500 },
        tdee: { preferred: 2557, minimum: 2400 },
        protein: { preferred: 145, minimum: 120 },
        carbohydrate: { preferred: 240, minimum: 200 },
        total_fat: { preferred: 70, minimum: 50 },
      },
    } as never,
    null,
    "2026-09-09",
  );

  expect(summary.targetCalories).toBe(2778);
  expect(summary.estimatedDailyExpenditureCalories).toBe(2557);
  expect(summary.protein).toBe(145);
  expect(summary.carbohydrate).toBe(240);
  expect(summary.fat).toBe(70);
});

it("returns an empty nutrition state when neither plan nor estimate exists", () => {
  expect(nutritionSummary(null, null, null, "2026-09-09")).toMatchObject({
    status: "empty",
    estimatedDailyExpenditureCalories: null,
    targetCalories: null,
    progress: 0,
  });
});

it("keeps gain and loss nutrition progress independent from tracked intake", () => {
  const estimate = {
    targets: {
      tdee: { preferred: 2400 },
      protein: { preferred: 145 },
      carbohydrate: { preferred: 240 },
      total_fat: { preferred: 70 },
    },
  } as never;
  const gainSummary = nutritionSummary(
    {
      days: [{ nutrient_totals: { energy_kcal: 3_000 }, plan_date: "2026-09-09" }],
      physician_approved: true,
    } as never,
    estimate,
    {
      actual_totals: { energy_kcal: 1_800 },
      check_in_status: null,
      data_status: "sufficient",
      entries: [],
    } as never,
    "2026-09-09",
  );
  const lossSummary = nutritionSummary(
    {
      days: [{ nutrient_totals: { energy_kcal: 1_800 }, plan_date: "2026-09-09" }],
      physician_approved: true,
    } as never,
    estimate,
    {
      actual_totals: { energy_kcal: 2_000 },
      check_in_status: null,
      data_status: "sufficient",
      entries: [],
    } as never,
    "2026-09-09",
  );

  expect(gainSummary.progress).toBeCloseTo(3000 / 2400);
  expect(lossSummary.progress).toBeCloseTo(1800 / 2400);
});
