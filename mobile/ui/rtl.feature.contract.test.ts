import { readFile } from "node:fs/promises";

import { expect, it } from "vitest";

type TextContract = {
  readonly align: "auto" | "center" | "left" | "right";
  readonly file: string;
  readonly style: string;
};

const contracts: readonly TextContract[] = [
  { align: "auto", file: "../accountDeletion/AccountDeletionScreen.tsx", style: "muted" },
  { align: "center", file: "../bodyAnalysis/BodyAnalysisEmptyState.tsx", style: "stepNumber" },
  { align: "center", file: "../bodyAnalysis/BodyAnalysisMuscleSection.tsx", style: "summaryChipText" },
  { align: "center", file: "../bodyAnalysis/BodyAnalysisMuscleSection.tsx", style: "viewBadgeText" },
  { align: "center", file: "../bodyAnalysis/BodyAnalysisOverviewCard.tsx", style: "captureText" },
  { align: "center", file: "../bodyAnalysis/BodyAnalysisOverviewCard.tsx", style: "mediaTagText" },
  { align: "center", file: "../bodyAnalysis/BodyAnalysisOverviewCard.tsx", style: "viewTabText" },
  { align: "auto", file: "../bodyAnalysis/BodyAnalysisResultScreen.tsx", style: "status" },
  { align: "center", file: "../exercises/ExerciseCatalogScreen.tsx", style: "contentBadge" },
  { align: "center", file: "../exercises/ExerciseCatalogScreen.tsx", style: "mediaDifficulty" },
  { align: "center", file: "../home/MemberHomeScreen.tsx", style: "avatarText" },
  { align: "center", file: "../home/WorkoutTodayCard.tsx", style: "statusText" },
  { align: "center", file: "../nutrition/NutritionDoctorSupervision.tsx", style: "itemTag" },
  { align: "auto", file: "../nutrition/NutritionSummaryCard.tsx", style: "breakdownText" },
  { align: "auto", file: "../nutrition/NutritionSummaryCard.tsx", style: "statusText" },
  { align: "auto", file: "../onboarding/OnboardingScreen.tsx", style: "progress" },
  { align: "auto", file: "../onboarding/OnboardingScreen.tsx", style: "questionProgress" },
  { align: "center", file: "../physician/PhysicianNutritionReviewScreen.tsx", style: "memberAvatarText" },
  { align: "center", file: "../profile/ProfilePhotoControl.tsx", style: "avatarText" },
  { align: "center", file: "../profile/ProfilePhotoControl.tsx", style: "deleteText" },
  { align: "center", file: "../profile/ProfileScreen.tsx", style: "avatarText" },
  { align: "center", file: "../profile/ProfileScreen.tsx", style: "optionalBadge" },
  { align: "auto", file: "../workouts/WorkoutCyclePanel.tsx", style: "cycleStatus" },
  { align: "auto", file: "../workouts/WorkoutPlansScreen.tsx", style: "secondaryDayTitle" },
  { align: "center", file: "../coach/CoachWorkoutReviewScreen.tsx", style: "avatarText" },
];

const technicalContracts: readonly TextContract[] = [
  { align: "center", file: "../bodyAnalysis/BodyAnalysisOverviewCard.tsx", style: "indicatorScore" },
  { align: "right", file: "../bodyAnalysis/BodyAnalysisOverviewCard.tsx", style: "metricValue" },
  { align: "center", file: "../bodyAnalysis/BodyAnalysisRequirements.tsx", style: "statusMarkText" },
  { align: "center", file: "../bodyAnalysis/BodyAnalysisRequirements.tsx", style: "stepBadge" },
  { align: "center", file: "../bodyAnalysis/BodyPhotoCapture.tsx", style: "scaleValue" },
  { align: "center", file: "../exercises/ExerciseCatalogScreen.tsx", style: "removeFilterGlyph" },
  { align: "center", file: "../exercises/ExerciseDetailScreen.tsx", style: "instructionNumber" },
  { align: "center", file: "../exercises/ExerciseMediaCarousel.tsx", style: "indicatorText" },
  { align: "right", file: "../home/NutritionSummaryCard.tsx", style: "calorieValue" },
  { align: "center", file: "../nutrition/NutritionDualMetricRing.tsx", style: "label" },
  { align: "center", file: "../nutrition/NutritionDualMetricRing.tsx", style: "value" },
  { align: "left", file: "../nutrition/NutritionScienceDetails.tsx", style: "metadataValue" },
  { align: "right", file: "../nutrition/NutritionScienceDetails.tsx", style: "micronutrientValue" },
  { align: "right", file: "../nutrition/NutritionScienceDetails.tsx", style: "targetValue" },
  { align: "right", file: "../nutrition/NutritionSummaryCard.tsx", style: "calorieValue" },
  { align: "right", file: "../nutrition/NutritionSummaryCard.tsx", style: "tdeeValue" },
  { align: "right", file: "../nutrition/NutritionSummaryCard.tsx", style: "metricValue" },
  { align: "center", file: "../nutrition/NutritionTrackingSection.tsx", style: "checkboxMark" },
  { align: "center", file: "../ui/components/MetricRing.tsx", style: "value" },
  { align: "center", file: "../ui/components/Overlay.tsx", style: "closeGlyph" },
  { align: "center", file: "../workouts/WorkoutCyclePanel.tsx", style: "summaryMetricValueAqua" },
  { align: "center", file: "../workouts/WorkoutPlansScreen.tsx", style: "reviewIndicatorApproved" },
  { align: "center", file: "../workouts/WorkoutPlansScreen.tsx", style: "reviewIndicatorRejected" },
];

function extractStyleBlock(source: string, styleName: string): string {
  const marker = `\n  ${styleName}: {`;
  const markerIndex = source.indexOf(marker);
  if (markerIndex < 0) return "";
  const openIndex = markerIndex + marker.lastIndexOf("{");
  if (openIndex < 0) return "";

  let depth = 0;
  let quote: string | null = null;
  let escaped = false;
  for (let index = openIndex; index < source.length; index += 1) {
    const character = source[index];
    if (quote !== null) {
      if (escaped) escaped = false;
      else if (character === "\\") escaped = true;
      else if (character === quote) quote = null;
      continue;
    }
    if (character === '"' || character === "'" || character === "`") {
      quote = character;
      continue;
    }
    if (character === "{") depth += 1;
    if (character === "}" && --depth === 0) return source.slice(openIndex, index + 1);
  }
  return "";
}

it("keeps normal Persian feature text explicitly aligned and directional", async () => {
  for (const contract of contracts) {
    const source = await readFile(new URL(contract.file, import.meta.url), "utf8");
    const style = extractStyleBlock(source, contract.style);
    const sharedDirection = contract.align === "center" ? "...RTL_CENTER_TEXT" : "...RTL_TEXT";
    const hasExplicitDirection = style.includes(sharedDirection)
      || (style.includes(`textAlign: "${contract.align}"`) && style.includes('writingDirection: "rtl"'));
    expect(hasExplicitDirection, `${contract.file} ${contract.style}`).toBe(true);
  }
});

it("keeps technical and numeric values LTR without changing their RTL container", async () => {
  for (const contract of technicalContracts) {
    const source = await readFile(new URL(contract.file, import.meta.url), "utf8");
    const style = extractStyleBlock(source, contract.style);
    expect(style, `${contract.file} ${contract.style}`).toContain(`textAlign: "${contract.align}"`);
    expect(style, `${contract.file} ${contract.style}`).toContain('writingDirection: "ltr"');
  }
});
