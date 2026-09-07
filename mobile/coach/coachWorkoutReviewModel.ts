import type { components } from "@fitician/core";

export type CoachReviewStatus = components["schemas"]["WorkoutReviewStatus"];
export type CoachReviewDraft = components["schemas"]["WorkoutReviewDraftUpdate"];

export function getCoachDraft(
  detail: Pick<components["schemas"]["WorkoutReviewDetailResponse"], "coach_note" | "draft" | "draft_revision">,
): CoachReviewDraft {
  const days = detail.draft?.days;
  return {
    coach_note: detail.coach_note,
    days: (Array.isArray(days) ? days : []) as CoachReviewDraft["days"],
    expected_revision: detail.draft_revision,
  };
}

export function hasRequiredRejectionExplanation(explanation: string): boolean {
  return explanation.trim().length > 0;
}

export function isCoachReviewReadOnly(status: CoachReviewStatus, offline: boolean): boolean {
  return offline || status === "approved" || status === "superseded";
}

export function coachReviewStatusLabel(status: CoachReviewStatus): string {
  const labels: Record<CoachReviewStatus, string> = {
    pending: "در انتظار بررسی",
    claimed: "در حال بررسی",
    approved: "تأییدشده",
    rejected: "برگشت‌داده‌شده برای اصلاح",
    superseded: "بایگانی‌شده",
  };
  return labels[status];
}

export function coachReviewErrorMessage(error: unknown): string {
  const code = error instanceof Error && "code" in error
    ? (error as { readonly code?: unknown }).code
    : null;
  if (code === "STALE_DRAFT_REVISION") {
    return "نسخهٔ پرونده تغییر کرده است؛ آن را دوباره دریافت کن.";
  }
  if (code === "REVIEW_LEASE_EXPIRED") {
    return "زمان بررسی تمام شده است؛ پرونده را دوباره باز کن.";
  }
  if (code === "REVIEW_ALREADY_CLAIMED") {
    return "این پرونده در اختیار مربی دیگری است.";
  }
  return "عملیات بازبینی انجام نشد؛ اتصال و وضعیت پرونده را بررسی کن.";
}
