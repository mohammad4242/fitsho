import {
  formatPrescriptionTarget,
  formatTomanInput,
  irrToRoundedToman,
  irrToToman,
  roundToTenThousandToman,
  tomanToIrr,
} from "./formatters.js";
import type { WorkoutPlanExercise } from "./workouts.js";

declare const exercise: WorkoutPlanExercise;

void formatPrescriptionTarget(exercise, "fa");
void formatTomanInput("۱۲۳");
void tomanToIrr("123");
void irrToToman(1_000);
void roundToTenThousandToman(10_000);
void irrToRoundedToman(100_000);
