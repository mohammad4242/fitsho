import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

const source = readFileSync(new URL("./PhysicianNutritionReviewScreen.tsx", import.meta.url), "utf8");

it("keeps the native physician workflow role-scoped and revision-safe", () => {
  expect(source).toContain("createPhysicianNutritionReviewApi");
  expect(source).toContain("getAccess");
  expect(source).toContain("input_snapshot");
  expect(source).toContain("warning_codes");
  expect(source).toContain("adjustFoodQuantity");
  expect(source).toContain("replaceFood");
  expect(source).toContain("expectedPlanRevisionId");
  expect(source).toContain("request_changes");
  expect(source).toContain("reject");
  expect(source).toContain("connectivityStatus");
  expect(source).toContain("readOnly");
});
