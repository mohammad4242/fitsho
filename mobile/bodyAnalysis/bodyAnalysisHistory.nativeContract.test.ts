import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

it("keeps body-analysis history member-scoped and deletion explicit", async () => {
  const source = await readFile(resolve(import.meta.dirname, "BodyAnalysisHistoryScreen.tsx"), "utf8");

  expect(source).toMatch(/getTimeline/);
  expect(source).toMatch(/deleteSession/);
  expect(source).toMatch(/BodyAnalysisDeleteDialog/);
  expect(source).toContain("/member/body-analysis-result/");
  expect(source).toContain("/member/body-analysis-capture");
  expect(source).not.toContain("/admin/");
  expect(source).not.toMatch(/console\.|Log\./);
});
