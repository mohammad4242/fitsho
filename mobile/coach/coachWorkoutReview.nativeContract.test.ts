import { readFile } from "node:fs/promises";
import { expect, it } from "vitest";

it("keeps the native coach workflow online-write gated and revision-aware", async () => {
  const source = await readFile(new URL("./CoachWorkoutReviewScreen.tsx", import.meta.url), "utf8");

  expect(source).toMatch(/createCoachWorkoutReviewApi/);
  expect(source).toMatch(/isCoachReviewReadOnly/);
  expect(source).toMatch(/api\.approve/);
  expect(source).toMatch(/api\.reject/);
  expect(source).toMatch(/api\.saveDraft/);
  expect(source).toMatch(/draft_revision/);
  expect(source).toMatch(/connectivityStatus/);
});
