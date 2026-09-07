import type { NotificationResponse } from "expo-notifications";

export type NotificationRoutePath =
  | "/coach"
  | "/member"
  | "/member/body-analysis-history"
  | "/member/nutrition"
  | "/member/workouts"
  | "/physician";

const notificationRoutes: Readonly<Record<string, NotificationRoutePath>> = {
  body_analysis_completed: "/member/body-analysis-history",
  body_analysis_failed: "/member/body-analysis-history",
  cycle_completion_feedback_due: "/member/workouts",
  nutrition_plan_approved: "/member/nutrition",
  nutrition_review_required: "/physician",
  physician_changes_requested: "/member/nutrition",
  physician_labs_requested: "/member/nutrition",
  physician_plan_approved: "/member/nutrition",
  physician_plan_rejected: "/member/nutrition",
  weekly_check_in_due: "/member/workouts",
  workout_plan_approved: "/member/workouts",
  workout_review_required: "/coach",
};

const notificationRoutePaths = new Set<NotificationRoutePath>([
  "/coach",
  "/member",
  "/member/body-analysis-history",
  "/member/nutrition",
  "/member/workouts",
  "/physician",
]);

export function isNotificationRoutePath(value: string): value is NotificationRoutePath {
  return notificationRoutePaths.has(value as NotificationRoutePath);
}

export function notificationPathFromData(data: unknown): NotificationRoutePath | null {
  if (!isRecord(data)) return null;
  const nestedData = isRecord(data.data) ? data.data : data;
  const eventType = nestedData.event_type;
  if (typeof eventType !== "string") return null;
  if (eventType === "body_analysis_review_required") {
    const role = nestedData.recipient_role;
    if (role === "coach") return "/coach";
    if (role === "doctor" || role === "physician") return "/physician";
    return null;
  }
  return notificationRoutes[eventType] ?? null;
}

export function notificationPathFromResponse(
  response: NotificationResponse | null | undefined,
): NotificationRoutePath | null {
  return notificationPathFromData(response?.notification.request.content.data);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
