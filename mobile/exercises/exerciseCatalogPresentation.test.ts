import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";

it("keeps exercise results prominent and moves advanced filters into a sheet", async () => {
  const source = await readFile(new URL("./ExerciseCatalogScreen.tsx", import.meta.url), "utf8");

  expect(source).toContain("Sheet");
  expect(source).toContain("activeFilterCount");
  expect(source.indexOf("نتایج حرکات")).toBeLessThan(source.indexOf("فیلترهای پیشرفته"));
});
