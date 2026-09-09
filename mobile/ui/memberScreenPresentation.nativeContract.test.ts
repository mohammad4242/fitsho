import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";

it("keeps secondary member screens on the shared Fitician hierarchy", async () => {
  const sources = await Promise.all([
    readFile(new URL("../nutrition/NutritionFoundationScreen.tsx", import.meta.url), "utf8"),
    readFile(new URL("../bodyAnalysis/BodyAnalysisHistoryScreen.tsx", import.meta.url), "utf8"),
    readFile(new URL("../bodyAnalysis/BodyAnalysisResultScreen.tsx", import.meta.url), "utf8"),
    readFile(new URL("../profile/ProfileScreen.tsx", import.meta.url), "utf8"),
    readFile(new URL("../auth/AuthScaffold.tsx", import.meta.url), "utf8"),
  ]);

  expect(sources[0]).toContain("PageHeading");
  expect(sources[0]).not.toContain("ScreenHeader");
  expect(sources[1]).toContain("ScreenHeader");
  expect(sources[2]).toContain("ScreenHeader");
  expect(sources[3]).toContain("ScreenHeader");
  expect(sources[4]).toContain("CinematicSurface");
});
