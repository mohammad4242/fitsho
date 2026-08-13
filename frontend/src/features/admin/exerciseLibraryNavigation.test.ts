import { expect, it } from "vitest";

import { exerciseLibraryReturnPath, readExerciseCreateContext } from "./exerciseLibraryNavigation";

it("reads matching upper, lower, and core create contexts", () => {
  expect(readExerciseCreateContext(new URLSearchParams("body_region=upper_body&primary_muscle=shoulders"))).toEqual({ body_region: "upper_body", primary_muscle: "shoulders" });
  expect(readExerciseCreateContext(new URLSearchParams("body_region=lower_body&primary_muscle=quadriceps"))).toEqual({ body_region: "lower_body", primary_muscle: "quadriceps" });
  expect(readExerciseCreateContext(new URLSearchParams("body_region=core&primary_muscle=abs"))).toEqual({ body_region: "core", primary_muscle: "abs" });
});

it("rejects mismatched create context and external return paths", () => {
  expect(readExerciseCreateContext(new URLSearchParams("body_region=upper_body&primary_muscle=quadriceps"))).toEqual({});
  expect(exerciseLibraryReturnPath("https://evil.test", "upper_body", "chest", true, false)).toBe("/exercises?body_region=upper_body&primary_muscle=chest");
});

it("returns to the saved category and clears filters that could hide the exercise", () => {
  expect(exerciseLibraryReturnPath(
    "/exercises?body_region=upper_body&primary_muscle=chest&equipment=barbell&difficulty=advanced&search=old&page=3",
    "lower_body",
    "quadriceps",
    false,
    false,
  )).toBe("/exercises?body_region=lower_body&primary_muscle=quadriceps&admin_status=inactive");
});

it("returns review records without a category through the protected review filter", () => {
  expect(exerciseLibraryReturnPath("/exercises?body_region=upper_body", null, null, true, true)).toBe("/exercises?admin_status=needs_review");
});
