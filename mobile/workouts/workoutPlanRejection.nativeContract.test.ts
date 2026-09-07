import { readFile } from "node:fs/promises";
import { expect, it } from "vitest";

it("shows coach rejection explanations to the member", async () => {
  const source = await readFile(new URL("./WorkoutPlansScreen.tsx", import.meta.url), "utf8");

  expect(source).toContain('state === "coach_rejected"');
  expect(source).toContain("coach_review.coach_note");
});
