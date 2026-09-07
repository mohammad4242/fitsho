import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const nutritionDirectory = dirname(fileURLToPath(import.meta.url));

it("ports adherence history with the backend causality notice", async () => {
  const source = await readFile(resolve(nutritionDirectory, "NutritionAdherenceSection.tsx"), "utf8");

  expect(source).toMatch(/getAdherence/);
  expect(source).toMatch(/getTrackingHistory/);
  expect(source).toMatch(/weight_causality_claimed/);
  expect(source).toMatch(/tracking_completeness/);
  expect(source).toMatch(/insufficient_data/);
});
