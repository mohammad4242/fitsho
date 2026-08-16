import { expect, it } from "vitest";

import { muscleFocusesByMuscle } from "./types";

it("does not expose quadriceps focus subcategories", () => {
  expect(muscleFocusesByMuscle.quadriceps).toEqual([]);
});

it("does not expose adductors focus subcategories", () => {
  expect(muscleFocusesByMuscle.adductors).toEqual([]);
});
