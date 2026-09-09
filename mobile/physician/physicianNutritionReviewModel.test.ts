import { expect, it } from "vitest";

import type { components } from "@fitician/core";

import {
  hasRequiredPhysicianDecisionNotes,
  isPhysicianPlanReadOnly,
  physicianReviewStatusLabel,
  selectMedicalContext,
  samePhysicianPlanRevision,
} from "./physicianNutritionReviewModel";

const plan = {
  id: "plan-1",
  revision: 3,
  review_status: "in_review",
  input_snapshot: {
    medical_conditions: ["kidney_disease"],
    medications: [{ name: "Medication A", dosage: "10 mg" }],
    physician_dietary_restrictions: "Low sodium",
  },
  warning_codes: ["PHYSICIAN_REVIEW_REQUIRED"],
} as unknown as components["schemas"]["WeeklyPlanResponse"];

it("extracts the medical context and preserves explicit warnings", () => {
  expect(selectMedicalContext(plan)).toEqual({
    conditions: ["kidney_disease"],
    medications: [{ name: "Medication A", dosage: "10 mg" }],
    restrictions: "Low sodium",
    safetyOutcome: null,
    safetyReasonCodes: [],
    warnings: ["PHYSICIAN_REVIEW_REQUIRED"],
  });
});

it("keeps offline and terminal physician plans read-only", () => {
  expect(isPhysicianPlanReadOnly("in_review", false)).toBe(false);
  expect(isPhysicianPlanReadOnly("in_review", true)).toBe(true);
  expect(isPhysicianPlanReadOnly("approved", false)).toBe(true);
  expect(isPhysicianPlanReadOnly("rejected", false)).toBe(true);
});

it("requires decision notes and detects revision changes", () => {
  expect(hasRequiredPhysicianDecisionNotes("  ")).toBe(false);
  expect(hasRequiredPhysicianDecisionNotes("Needs lower sodium.")).toBe(true);
  expect(samePhysicianPlanRevision(plan, { ...plan })).toBe(true);
  expect(samePhysicianPlanRevision(plan, { ...plan, id: "plan-2" })).toBe(false);
  expect(samePhysicianPlanRevision(plan, { ...plan, revision: 4 })).toBe(false);
});

it("labels the review states for the specialist queue", () => {
  expect(physicianReviewStatusLabel("pending")).toBe("در انتظار بررسی");
  expect(physicianReviewStatusLabel("in_review")).toBe("در حال بررسی");
  expect(physicianReviewStatusLabel("changes_requested")).toBe("نیازمند اصلاح");
  expect(physicianReviewStatusLabel("approved")).toBe("تأییدشده");
  expect(physicianReviewStatusLabel("rejected")).toBe("ردشده");
  expect(physicianReviewStatusLabel("unknown_internal_status")).toBe("نیازمند بررسی");
});
