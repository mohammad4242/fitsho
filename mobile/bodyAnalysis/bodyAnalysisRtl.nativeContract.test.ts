import { readFile } from "node:fs/promises";
import { expect, it } from "vitest";

const bodyAnalysisFiles = [
  "BodyAnalysisCameraButton.tsx",
  "BodyAnalysisDeleteDialog.tsx",
  "BodyAnalysisEmptyState.tsx",
  "BodyAnalysisLandingHero.tsx",
  "BodyAnalysisMuscleSection.tsx",
  "BodyAnalysisOverviewCard.tsx",
  "BodyAnalysisRequirements.tsx",
  "BodyAnalysisResultScreen.tsx",
  "BodyAnalysisStartCard.tsx",
  "BodyBeforeAfterComparison.tsx",
  "BodyPhotoCapture.tsx",
  "BodyProgressComparison.tsx",
  "BodyProgressTimeline.tsx",
] as const;

it("keeps body-analysis layout on native RTL primitives", async () => {
  const sources = await Promise.all(
    bodyAnalysisFiles.map((file) => readFile(new URL(`./${file}`, import.meta.url), "utf8")),
  );

  for (const source of sources) {
    expect(source).not.toContain('flexDirection: "row-reverse"');
    expect(source).not.toContain('alignItems: "flex-end"');
  }
});

it("keeps the Body Analysis product mark explicitly LTR", async () => {
  const source = await readFile(new URL("./BodyAnalysisLandingHero.tsx", import.meta.url), "utf8");

  expect(source).toContain('textAlign: "left"');
  expect(source).toContain('writingDirection: "ltr"');
});
