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
  expect(source).toContain("PageHeading");
  expect(source).toContain("SegmentedControl");
  expect(source).toContain("useAndroidBackHandler");
  expect(source).toContain("clinicalTab");
  expect(source).toContain("requestLabs");
  expect(source).toContain("reviewLab");
  expect(source).toContain("supplement-orders");
  expect(source).toContain("مکمل‌ها");
});

it("keeps physician-facing technical codes behind Persian presentation labels", () => {
  expect(source).not.toContain("safety_reason_codes.join");
  expect(source).not.toContain("medical_condition_policy_version}");
  expect(source).not.toContain("formula_version}");
  expect(source).not.toContain("status.replaceAll");
  expect(source).not.toContain("return error instanceof Error && error.message");
});

it("keeps physician review layout logical for native RTL", () => {
  expect(source).toMatch(/<Screen contentWidth="reading">/);
  expect(source).toContain('textAlign: "right"');
  expect(source).toContain('writingDirection: "rtl"');
  expect(source).toMatch(
    /<View style=\{styles\.orderHeader\}>\s*<View style=\{styles\.headerCopy\}>[\s\S]*?<Text style=\{styles\.status\}>/,
  );
  expect(source).toMatch(
    /<View style=\{styles\.caseIdentity\}>\s*<View style=\{styles\.headerCopy\}>[\s\S]*?<View accessibilityLabel=\{`تصویر \$\{memberName\}`} style=\{styles\.memberAvatar\}>/,
  );
});
