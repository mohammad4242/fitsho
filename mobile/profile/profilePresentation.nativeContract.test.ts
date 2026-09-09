import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

it("keeps profile presentation grouped around real account data", async () => {
  const source = await readFile(resolve(import.meta.dirname, "ProfileScreen.tsx"), "utf8");

  expect(source).toMatch(/ProfileOverviewCard/);
  expect(source).toMatch(/shared\.fitness_goal/);
  expect(source).toMatch(/shared\.height_cm/);
  expect(source).toMatch(/shared\.current_weight_kg/);
  expect(source).toMatch(/AccountPrivacyLinks/);
});
