import type { components } from "@fitician/core";

export type PhysicianNutritionPlan = components["schemas"]["WeeklyPlanResponse"];

export type PhysicianMedicalContext = {
  readonly conditions: string[];
  readonly medications: Array<{ readonly dosage: string | null; readonly name: string }>;
  readonly restrictions: string | null;
  readonly safetyOutcome: string | null;
  readonly safetyReasonCodes: string[];
  readonly warnings: string[];
};

export function hasRequiredPhysicianDecisionNotes(notes: string): boolean {
  return notes.trim().length > 0;
}

export function isPhysicianPlanReadOnly(reviewStatus: string, offline: boolean): boolean {
  return offline || ["approved", "rejected", "invalidated_by_revision"].includes(reviewStatus);
}

export function physicianReviewStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    approved: "تأییدشده",
    awaiting_lab_information: "در انتظار آزمایش",
    changes_requested: "نیازمند اصلاح",
    in_review: "در حال بررسی",
    invalidated_by_revision: "نسخه منقضی‌شده",
    pending: "در انتظار بررسی",
    rejected: "ردشده",
  };
  return labels[status] ?? status.replaceAll("_", " ");
}

export function samePhysicianPlanRevision(
  current: Pick<PhysicianNutritionPlan, "id" | "revision" | "review_status">,
  latest: Pick<PhysicianNutritionPlan, "id" | "revision" | "review_status">,
): boolean {
  return current.id === latest.id
    && current.revision === latest.revision
    && current.review_status === latest.review_status;
}

export function selectMedicalContext(plan: Pick<PhysicianNutritionPlan, "input_snapshot" | "warning_codes">): PhysicianMedicalContext {
  const snapshot = plan.input_snapshot;
  return {
    conditions: firstStringArray(snapshot, ["medical_conditions", "conditions", "safety_conditions"]),
    medications: medicationRows(snapshot.medications),
    restrictions: firstString(snapshot, ["physician_dietary_restrictions", "medical_restrictions"]),
    safetyOutcome: firstString(snapshot, ["safety_outcome"]),
    safetyReasonCodes: firstStringArray(snapshot, ["safety_reason_codes"]),
    warnings: plan.warning_codes,
  };
}

function firstString(snapshot: Record<string, unknown>, keys: string[]): string | null {
  for (const key of keys) {
    const value = snapshot[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return null;
}

function firstStringArray(snapshot: Record<string, unknown>, keys: string[]): string[] {
  for (const key of keys) {
    const value = snapshot[key];
    if (Array.isArray(value)) {
      return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
    }
  }
  return [];
}

function medicationRows(value: unknown): PhysicianMedicalContext["medications"] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (typeof item === "string" && item.trim()) return [{ dosage: null, name: item.trim() }];
    if (item === null || typeof item !== "object") return [];
    const row = item as { readonly dosage?: unknown; readonly name?: unknown };
    if (typeof row.name !== "string" || !row.name.trim()) return [];
    return [{
      dosage: typeof row.dosage === "string" && row.dosage.trim() ? row.dosage.trim() : null,
      name: row.name.trim(),
    }];
  });
}
