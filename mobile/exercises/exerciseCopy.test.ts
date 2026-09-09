import { expect, it } from "vitest";

import { exerciseTitle } from "./exerciseCopy";

it("shows only the selected localized exercise name with a safe fallback", () => {
  const localizedTitle = exerciseTitle as unknown as (nameFa: string, nameEn: string, language: "fa" | "en") => string;

  expect(localizedTitle("پرس بالا سینه دمبل", "Dumbbell Incline Bench Press", "fa")).toBe("پرس بالا سینه دمبل");
  expect(localizedTitle("پرس بالا سینه دمبل", "Dumbbell Incline Bench Press", "en")).toBe("Dumbbell Incline Bench Press");
  expect(localizedTitle("", "Dumbbell Incline Bench Press", "fa")).toBe("Dumbbell Incline Bench Press");
});
