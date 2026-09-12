import { expect, it } from "vitest";

import {
  deriveHomeTrainingSetupFromEquipment,
  equipmentForHomeTrainingSetup,
  homeTrainingSetups,
  homeTrainingSetupEquipment,
} from "./profile.js";
import en from "./i18n/en.js";
import fa from "./i18n/fa.js";

const expectedEquipment = {
  bodyweight_only: ["bodyweight", "pull_up_bar"],
  dumbbells_available: ["bodyweight", "dumbbell", "pull_up_bar"],
  resistance_bands_available: ["bodyweight", "resistance_band", "pull_up_bar"],
  dumbbells_and_resistance_bands_available: [
    "bodyweight",
    "dumbbell",
    "resistance_band",
    "pull_up_bar",
  ],
} as const;

it("defines the four canonical home training presets", () => {
  expect(homeTrainingSetups).toEqual([
    "bodyweight_only",
    "dumbbells_available",
    "resistance_bands_available",
    "dumbbells_and_resistance_bands_available",
  ]);

  for (const setup of homeTrainingSetups) {
    expect(homeTrainingSetupEquipment[setup]).toEqual(expectedEquipment[setup]);
    expect(equipmentForHomeTrainingSetup(setup)).toEqual(expectedEquipment[setup]);
    expect(equipmentForHomeTrainingSetup(setup)).not.toBe(homeTrainingSetupEquipment[setup]);
  }
});

it("derives the most capable supported preset from legacy equipment", () => {
  expect(deriveHomeTrainingSetupFromEquipment(["bodyweight", "pull_up_bar"])).toBe(
    "bodyweight_only",
  );
  expect(deriveHomeTrainingSetupFromEquipment(["bodyweight", "dumbbell", "pull_up_bar"])).toBe(
    "dumbbells_available",
  );
  expect(deriveHomeTrainingSetupFromEquipment(["bodyweight", "resistance_band", "pull_up_bar"])).toBe(
    "resistance_bands_available",
  );
  expect(
    deriveHomeTrainingSetupFromEquipment([
      "bodyweight",
      "dumbbell",
      "resistance_band",
      "pull_up_bar",
    ]),
  ).toBe("dumbbells_and_resistance_bands_available");
  expect(deriveHomeTrainingSetupFromEquipment(["bench"])).toBeNull();
});

it("translates all home presets without offering a pull-up-bar opt-out", () => {
  expect(fa.translation.onboarding.options.homeTrainingSetup).toEqual({
    bodyweight_only: "وزن بدن",
    dumbbells_available: "دمبل",
    resistance_bands_available: "کش",
    dumbbells_and_resistance_bands_available: "دمبل + کش",
  });
  expect(en.translation.onboarding.options.homeTrainingSetup).toEqual({
    bodyweight_only: "Bodyweight",
    dumbbells_available: "Dumbbells",
    resistance_bands_available: "Resistance band",
    dumbbells_and_resistance_bands_available: "Dumbbells + resistance band",
  });
  expect(fa.translation.onboarding.hints.homeTrainingSetup).not.toContain("تیک");
  expect(en.translation.onboarding.hints.homeTrainingSetup).not.toContain("uncheck");
});
