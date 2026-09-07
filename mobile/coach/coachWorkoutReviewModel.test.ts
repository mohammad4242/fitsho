import { expect, it } from "vitest";

import type { components } from "@fitician/core";

import {
  coachReviewStatusLabel,
  getCoachDraft,
  hasRequiredRejectionExplanation,
  isCoachReviewReadOnly,
} from "./coachWorkoutReviewModel";

const detail = {
  coach_note: "یادداشت قبلی",
  draft_revision: 4,
  draft: {
    days: [
      {
        day_number: 1,
        exercises: [
          {
            order_index: 1,
            exercise_id: "exercise-1",
            sets: 3,
            prescription_mode: "reps",
            reps_min: 8,
            reps_max: 12,
            rir: 2,
            rest_seconds: 90,
            notes_en: null,
            notes_fa: "کنترل حرکت",
          },
        ],
      },
    ],
  },
} as unknown as components["schemas"]["WorkoutReviewDetailResponse"];

it("normalizes the server draft into the next revision payload", () => {
  expect(getCoachDraft(detail)).toEqual({
    coach_note: "یادداشت قبلی",
    days: detail.draft?.days,
    expected_revision: 4,
  });
});

it("requires a non-blank explanation before a coach can reject a review", () => {
  expect(hasRequiredRejectionExplanation("  ")).toBe(false);
  expect(hasRequiredRejectionExplanation("نیاز به اصلاح دارد")).toBe(true);
});

it("keeps approved and offline coach reviews read-only", () => {
  expect(isCoachReviewReadOnly("approved", false)).toBe(true);
  expect(isCoachReviewReadOnly("claimed", true)).toBe(true);
  expect(isCoachReviewReadOnly("claimed", false)).toBe(false);
});

it("uses explicit Persian status labels", () => {
  expect(coachReviewStatusLabel("pending")).toBe("در انتظار بررسی");
  expect(coachReviewStatusLabel("claimed")).toBe("در حال بررسی");
  expect(coachReviewStatusLabel("approved")).toBe("تأییدشده");
});
