import { readFile } from "node:fs/promises";

import { expect, it } from "vitest";

import { getResponsiveLayout } from "../ui/layoutMetrics";
import * as workoutModel from "./workoutModel";

it("uses the web-like workout page hierarchy without cinematic overview components", async () => {
  const source = await readFile(new URL("./WorkoutPlansScreen.tsx", import.meta.url), "utf8");

  expect(source).not.toContain("CinematicSurface");
  expect(source).not.toContain("MetricStrip");
  expect(source).not.toContain("ScreenHeader");
  expect(source).toContain("برنامه تمرینی من");
  expect(source).toContain("durationBadge");
  expect(source).toContain("contextStrip");
  expect(source).toContain("index > 0 && styles.contextCellDivided");
  expect(source).toContain('flex: 1');
  expect(source).toContain("برنامه فعلی");
  expect(source).toContain("روزهای تمرین");
  expect(source).toContain("زمان جلسه");
  expect(source).toContain("CoachReviewBanner");
  expect(source).toContain("reviewBanner");
  expect(source).toContain("GenerationMethodSelector");
  expect(source).toContain("SegmentedControl");
  expect(source).toContain("چه کسی برنامه‌ات را بنویسد؟");
  expect(source).toContain("هوش مصنوعی");
  expect(source).toContain("موتور داخلی");
  expect(source).toContain("برنامه هفتگی");
  expect(source).toContain("روزهای تمرین تو");
  expect(source).toContain("به‌روزرسانی برنامه");
  expect(source).not.toContain("برنامه شخصی تو");
  expect(source).not.toContain("برنامهٔ تمرینی هفتگی");
  expect(source).not.toContain("نکات ایمنی برنامه");
  expect(source).not.toContain("plan.warnings.join");
  expect(source).not.toContain("warnings.join");
  expect(source).toContain("getUserVisibleWorkoutWarnings");
  expect(source).toContain("createProfileApi(auth.request)");
  expect(source).toContain("profileApi.getProfile");
  expect(source).toContain("profileApi.updateProfile");
  expect(source).toContain("setGenerationMethod(previousMethod)");
  expect(source).toContain("disabled={saving}");
  expect(source).toContain("setGenerationMethodError");
  expect(source).toContain("queryClient.setQueryData(profileKeys.current(), profile)");
});

it("maps only supported warnings and filters internal warning codes", () => {
  const getUserVisibleWorkoutWarnings = (workoutModel as typeof workoutModel & {
    getUserVisibleWorkoutWarnings?: (warnings: readonly string[] | undefined) => string[];
  }).getUserVisibleWorkoutWarnings;

  expect(typeof getUserVisibleWorkoutWarnings).toBe("function");
  if (getUserVisibleWorkoutWarnings === undefined) return;

  const visible = getUserVisibleWorkoutWarnings([
    "SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE",
    "SOFT_WEEKLY_VOLUME_BELOW_MINIMUM",
    "PLANNED_VOLUME_REDUCED_DURING_SESSION_FIT",
  ]);

  expect(visible).toEqual(["برای حفظ اثربخشی برنامه، لطفاً زمان تمرین خود را کمی افزایش دهید."]);
  expect(visible.join("\n")).not.toContain("SOFT_WEEKLY_VOLUME_BELOW_MINIMUM");
  expect(visible.join("\n")).not.toContain("PLANNED_VOLUME_REDUCED_DURING_SESSION_FIT");
});

it("keeps expanded exercise details as separate web-parity stats and actions", async () => {
  const source = await readFile(new URL("./WorkoutPlansScreen.tsx", import.meta.url), "utf8");
  const row = source.slice(source.indexOf("function WorkoutExerciseRow"), source.indexOf("function WorkoutHistory"));

  expect(source).toContain("function WorkoutExerciseRow");
  expect(row).toContain("exercise.sets");
  expect(row).toContain("exercise.reps_min");
  expect(row).toContain("exercise.reps_max");
  expect(row).toContain("exercise.duration_min_seconds");
  expect(row).toContain("exercise.duration_max_seconds");
  expect(row).toContain("exercise.rest_seconds");
  expect(row).toContain("exercise.rir");
  expect(row).toContain("exercise.alternatives");
  expect(row).toContain("ست");
  expect(row).toContain("تکرار");
  expect(row).toContain("زمان");
  expect(row).toContain("استراحت");
  expect(row).toContain("RIR");
  expect(row).toContain("مشاهده جزئیات حرکت");
  expect(row).toContain("حرکت جایگزین");
  expect(row).toContain("styles.exerciseStatsRow");
  expect(row).toContain("styles.exerciseStatLabel");
  expect(row).toContain("styles.exerciseStatValue");
  expect(row).toContain("styles.exerciseAction");
  expect(row).toContain("styles.exerciseActionText");
  expect(row).toContain("onStartReplacement");
  expect(row).toContain("onOpen();");
  expect(row).toContain("onStartReplacement(exercise.id)");
  expect(row).toContain("event.stopPropagation()");
  expect(source).not.toContain("formatExerciseMetadata");
  expect(source).not.toContain("formatWorkoutPrescription(exercise)");
  expect(row).not.toContain('style={styles.exerciseStats}');
  expect(source).toContain("exerciseStatsRow:");
  expect(source).toContain("exerciseStatLabel:");
  expect(source).toContain("exerciseStatValue:");
  expect(source).toContain('textDecorationLine: "underline"');
  expect(source).toContain("onOpenExercise");
  expect(source).toContain('name={expanded ? "chevronUp" : "chevronDown"}');
  expect(source).toContain("accessibilityState={{ expanded }}");
  expect(source).not.toContain("statusStack");
});

it("keeps cycle, check-in, replacement, and completion behavior secondary to the plan", async () => {
  const source = await readFile(new URL("./WorkoutCyclePanel.tsx", import.meta.url), "utf8");
  const summary = source.slice(source.indexOf("function CycleSummary"), source.indexOf("function WeeklyCheckInPanel"));

  expect(summary).not.toContain("CinematicSurface");
  expect(summary).not.toContain("MetricStrip");
  expect(summary).toContain("summaryCard");
  expect(source).toContain("WeeklyCheckInPanel");
  expect(source).toContain("ReplacementPanel");
  expect(source).toContain("CompletionFeedbackPanel");
  expect(source).toContain("api.getWeeklyCheckIn");
  expect(source).toContain("api.recordReplacement");
  expect(source).toContain("api.getCompletionFeedback");
});

it("keeps the four context cells viable at the required phone widths", async () => {
  const source = await readFile(new URL("./WorkoutPlansScreen.tsx", import.meta.url), "utf8");
  const contextStrip = source.slice(source.indexOf("function PlanContextStrip"), source.indexOf("function CoachReviewBanner"));
  expect(contextStrip.match(/\{ label:/g)).toHaveLength(4);

  for (const width of [360, 390, 430]) {
    const contentWidth = getResponsiveLayout(width, 844).contentWidth;
    expect(contentWidth / 4 - 8).toBeGreaterThanOrEqual(74);
  }
  expect(source).toContain("styles.contextCell");
  expect(source).toContain("minWidth: 0");
  expect(source).toContain('width: "100%"');
});

it("keeps session duration compact and removes only stale informational notices", async () => {
  const source = await readFile(new URL("./WorkoutPlansScreen.tsx", import.meta.url), "utf8");

  expect(source).toContain('`${formatPersianNumber(averageDuration, { maximumFractionDigits: 0 })} دقیقه`');
  expect(source).not.toContain("برای هر جلسه");
  expect(source).not.toContain("این برنامه از حافظهٔ آفلاین خوانده شده و ممکن است تازه‌ترین نسخه نباشد.");
  expect(source).not.toContain("اطلاعات این برنامه قدیمی است؛ قبل از اجرا وضعیت آنلاین را بررسی کن.");
  expect(source).toContain("اتصال اینترنت برقرار نیست؛ آخرین برنامهٔ ذخیره‌شده نمایش داده می‌شود.");
});

it("keeps each exercise as one roomy detail action", async () => {
  const source = await readFile(new URL("./WorkoutPlansScreen.tsx", import.meta.url), "utf8");
  const row = source.slice(source.indexOf("function WorkoutExerciseRow"), source.indexOf("function WorkoutHistory"));

  expect(row).toContain("accessibilityLabel={`باز کردن راهنمای");
  expect(row).toContain("onOpen();");
  expect(row).toContain("onStartReplacement(exercise.id)");
  expect(row).not.toContain('label="راهنما"');
});

it("keeps workout media first in the existing RTL row containers", async () => {
  const source = await readFile(new URL("./WorkoutPlansScreen.tsx", import.meta.url), "utf8");
  const daySummary = source.slice(source.indexOf("daySummary:"), source.indexOf("durationBadge:"));
  const exerciseRow = source.slice(source.indexOf("exerciseRow:"), source.indexOf("readOnlyAlternatives:"));

  expect(daySummary).toContain('flexDirection: "row"');
  expect(daySummary).not.toContain('flexDirection: "row-reverse"');
  expect(exerciseRow).toContain('flexDirection: "row"');
  expect(exerciseRow).not.toContain('flexDirection: "row-reverse"');
});

it("shows alternatives independently of executability and keeps the web action order", async () => {
  const source = await readFile(new URL("./WorkoutPlansScreen.tsx", import.meta.url), "utf8");
  const row = source.slice(source.indexOf("function WorkoutExerciseRow"), source.indexOf("function WorkoutHistory"));

  expect(row).toContain("exercise.alternatives.length > 0");
  expect(row).not.toContain("onStartReplacement && exercise.alternatives.length > 0");
  expect(row).toContain("styles.exerciseAction");
  expect(row).toContain("styles.exerciseActionText");
  expect(row.indexOf("actionCopy.detail")).toBeLessThan(row.indexOf("actionCopy.alternatives"));
  expect(source).toContain('detail: "View exercise details"');
  expect(source).toContain('alternatives: "View alternatives"');
  expect(source).toContain("ReadOnlyAlternativeList");
  expect(source).toContain("alternative.reason_en");
  expect(source).toContain("alternative.reason_fa");
});

it("keeps executable replacement on the existing cycle flow and blocks non-executable submission", async () => {
  const source = await readFile(new URL("./WorkoutPlansScreen.tsx", import.meta.url), "utf8");

  expect(source).toContain("onStartReplacement(exercise.id)");
  expect(source).toContain("replacementRequest={replacementRequest}");
  expect(source).toContain("onStartReplacement={executable && !pending ? onStartReplacement : undefined}");
  expect(source).toContain("onStartReplacement ?");
  expect(source).toContain("setAlternativesExpanded");
  expect(source).toContain("onOpenAlternative");
});
