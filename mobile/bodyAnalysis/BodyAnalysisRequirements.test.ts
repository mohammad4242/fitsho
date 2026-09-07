import { expect, it } from "vitest";

import {
  measurementErrorMessage,
  measurementPatch,
  measurementValuesFromProfile,
} from "./bodyAnalysisRequirementsModel";

const profile = {
  current_weight_kg: 76.5,
  height_cm: 178,
  hip_circumference_cm: 99,
  shoulder_circumference_cm: 112,
  waist_circumference_cm: 82.5,
} as const;

it("maps the shared profile measurements into the native form", () => {
  expect(measurementValuesFromProfile(profile)).toEqual({
    current_weight_kg: "76.5",
    height_cm: "178",
    hip_circumference_cm: "99",
    shoulder_circumference_cm: "112",
    waist_circumference_cm: "82.5",
  });
});

it("writes only measurements that changed", () => {
  expect(measurementPatch({
    current_weight_kg: "76.5",
    height_cm: "180",
    hip_circumference_cm: "99",
    shoulder_circumference_cm: "114",
    waist_circumference_cm: "82.5",
  }, profile)).toEqual({ height_cm: 180, shoulder_circumference_cm: 114 });
});

it("keeps measurement validation copy specific to each field error", () => {
  expect(measurementErrorMessage("required")).toContain("لازم");
  expect(measurementErrorMessage("weightPrecision")).toContain("دو رقم");
  expect(measurementErrorMessage(undefined)).toBeUndefined();
});
