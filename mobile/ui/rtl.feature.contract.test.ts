import { readFile } from "node:fs/promises";

import { expect, it } from "vitest";

type TextContract = {
  readonly align: "center" | "right";
  readonly file: string;
  readonly style: string;
};

const contracts: readonly TextContract[] = [
  { align: "right", file: "../accountDeletion/AccountDeletionScreen.tsx", style: "muted" },
  { align: "center", file: "../bodyAnalysis/BodyAnalysisEmptyState.tsx", style: "stepNumber" },
  { align: "center", file: "../bodyAnalysis/BodyAnalysisMuscleSection.tsx", style: "summaryChipText" },
  { align: "center", file: "../bodyAnalysis/BodyAnalysisMuscleSection.tsx", style: "viewBadgeText" },
  { align: "center", file: "../bodyAnalysis/BodyAnalysisOverviewCard.tsx", style: "captureText" },
  { align: "center", file: "../bodyAnalysis/BodyAnalysisOverviewCard.tsx", style: "mediaTagText" },
  { align: "center", file: "../bodyAnalysis/BodyAnalysisOverviewCard.tsx", style: "viewTabText" },
  { align: "right", file: "../bodyAnalysis/BodyAnalysisResultScreen.tsx", style: "status" },
  { align: "center", file: "../exercises/ExerciseCatalogScreen.tsx", style: "contentBadge" },
  { align: "center", file: "../exercises/ExerciseCatalogScreen.tsx", style: "mediaDifficulty" },
  { align: "center", file: "../home/MemberHomeScreen.tsx", style: "avatarText" },
  { align: "center", file: "../home/WorkoutTodayCard.tsx", style: "statusText" },
  { align: "center", file: "../nutrition/NutritionDoctorSupervision.tsx", style: "itemTag" },
  { align: "right", file: "../nutrition/NutritionSummaryCard.tsx", style: "breakdownText" },
  { align: "right", file: "../nutrition/NutritionSummaryCard.tsx", style: "statusText" },
  { align: "right", file: "../onboarding/OnboardingScreen.tsx", style: "progress" },
  { align: "right", file: "../onboarding/OnboardingScreen.tsx", style: "questionProgress" },
  { align: "center", file: "../physician/PhysicianNutritionReviewScreen.tsx", style: "memberAvatarText" },
  { align: "center", file: "../profile/ProfilePhotoControl.tsx", style: "avatarText" },
  { align: "center", file: "../profile/ProfilePhotoControl.tsx", style: "deleteText" },
  { align: "center", file: "../profile/ProfileScreen.tsx", style: "avatarText" },
  { align: "center", file: "../profile/ProfileScreen.tsx", style: "optionalBadge" },
  { align: "right", file: "../workouts/WorkoutCyclePanel.tsx", style: "cycleStatus" },
  { align: "right", file: "../workouts/WorkoutPlansScreen.tsx", style: "secondaryDayTitle" },
  { align: "center", file: "../coach/CoachWorkoutReviewScreen.tsx", style: "avatarText" },
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
