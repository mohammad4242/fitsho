import { readFile } from "node:fs/promises";
import { expect, it } from "vitest";

it("uses a status-first native nutrition plan hierarchy", async () => {
  const route = await readFile(new URL("../app/(member)/member/nutrition-plan.tsx", import.meta.url), "utf8");
  const source = await readFile(new URL("./NutritionPlanSection.tsx", import.meta.url), "utf8");
  const shopping = await readFile(new URL("./NutritionShoppingList.tsx", import.meta.url), "utf8");

  expect(route).toContain("PageHeading");
  expect(route).not.toContain("ScreenHeader");
  expect(source).toContain("planRoleLabel");
  expect(source).toContain("planApprovalLabel");
  expect(source).toContain("برنامه فعال شما");
  expect(source).toContain("PlanChoiceMetric");
  expect(source).not.toContain("warning_codes.join");
  expect(source).not.toContain("reason_codes.join");
  expect(shopping).not.toContain("warning_codes.join");
});
