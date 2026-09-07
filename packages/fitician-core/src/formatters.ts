import type { WorkoutPlanExercise } from "./workouts.js";

const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

export function formatTomanInput(value: string): string {
  const latin = value.replace(/[۰-۹]/g, (digit) => String(PERSIAN_DIGITS.indexOf(digit)));
  const digits = latin.replaceAll(/\D/g, "").replace(/^0+(?=\d)/, "");
  return digits ? Number(digits).toLocaleString("en-US", { useGrouping: true }) : "";
}

export function tomanToIrr(value: string): number {
  const normalized = formatTomanInput(value).replaceAll(",", "");
  return normalized ? Number(normalized) * 10 : 0;
}

export function irrToToman(value: number): string {
  return formatTomanInput(String(Math.floor(value / 10)));
}

export function roundToTenThousandToman(toman: number): number {
  if (toman <= 0) return 0;
  const rounded = Math.round(toman / 10_000) * 10_000;
  return rounded === 0 ? 10_000 : rounded;
}

export function irrToRoundedToman(irr: number): number {
  return roundToTenThousandToman(Math.floor(irr / 10));
}

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
