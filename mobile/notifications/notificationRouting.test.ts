import { expect, it } from "vitest";

import type { NotificationResponse } from "expo-notifications";

import {
  isNotificationRoutePath,
  notificationPathFromData,
  notificationPathFromResponse,
} from "./notificationRouting";

it("maps domain notification events to authenticated native destinations", () => {
  expect(notificationPathFromData({ event_type: "workout_plan_approved" })).toBe(
    "/member/workouts",
  );
  expect(notificationPathFromData({ event_type: "nutrition_plan_approved" })).toBe(
    "/member/nutrition",
  );
  expect(notificationPathFromData({ event_type: "food_photo_analysis_completed" })).toBe(
    "/member/nutrition",
  );
  expect(notificationPathFromData({ event_type: "food_photo_analysis_failed" })).toBe(
    "/member/nutrition",
  );
  expect(notificationPathFromData({ event_type: "body_analysis_completed" })).toBe(
    "/member/body-analysis-history",
  );
  expect(notificationPathFromData({ event_type: "weekly_check_in_due" })).toBe(
    "/member/workouts",
  );
  expect(notificationPathFromData({ event_type: "workout_review_required" })).toBe("/coach");
  expect(notificationPathFromData({ event_type: "nutrition_review_required" })).toBe(
    "/physician",
  );
  expect(
    notificationPathFromData({
      event_type: "body_analysis_review_required",
      recipient_role: "coach",
    }),
  ).toBe("/coach");
  expect(
    notificationPathFromData({
      event_type: "body_analysis_review_required",
      recipient_role: "doctor",
    }),
  ).toBe("/physician");
});

it("extracts notification data without trusting arbitrary routes or resource ids", () => {
  const response = {
    notification: {
      request: {
        content: {
          data: {
            event_type: "physician_plan_rejected",
            plan_id: "not-used-as-a-route",
            path: "/admin",
          },
        },
      },
    },
  } as unknown as NotificationResponse;

  expect(notificationPathFromResponse(response)).toBe("/member/nutrition");
  expect(notificationPathFromData({ event_type: "unknown_event", path: "/admin" })).toBeNull();
  expect(notificationPathFromData({ event_type: "body_analysis_review_required" })).toBeNull();
  expect(isNotificationRoutePath("/admin")).toBe(false);
  expect(isNotificationRoutePath("/member/workouts")).toBe(true);
  expect(notificationPathFromResponse(null)).toBeNull();
});
