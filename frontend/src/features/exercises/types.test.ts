import { expect, it } from "vitest";

import { muscleFocusesByMuscle } from "./types";
import { muscleGroups } from "./types";

it("does not expose quadriceps focus subcategories", () => {
  expect(muscleFocusesByMuscle.quadriceps).toEqual([]);
});

it("does not expose adductors focus subcategories", () => {
  expect(muscleFocusesByMuscle.adductors).toEqual([]);
});

it("exposes abductors and legs as lower-body muscle groups", () => {
  expect(muscleGroups).toEqual(expect.arrayContaining(["abductors", "legs"]));
});
