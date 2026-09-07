import { expect, it, vi } from "vitest";

import type { TransportRequest } from "@fitician/core";

import { createNotificationApi, type AuthenticatedNotificationRequest } from "./notificationApi";

it("uses the current-device notification and preference endpoints", async () => {
  const request = vi.fn<AuthenticatedNotificationRequest>(
    async <TResponse>(_input: TransportRequest): Promise<TResponse> => ({}) as TResponse,
  );
  const api = createNotificationApi(request as unknown as AuthenticatedNotificationRequest);

  await api.listDevices();
  await api.registerCurrentDevice("fcm-token");
  await api.getPreferences();
  await api.updatePreferences({
    enabled: true,
    approved_plans: false,
    required_reviews: true,
    body_analysis: false,
    cycle_reminders: true,
    physician_decisions: false,
  });
  await api.unregisterDevice("device/1");

  expect(request.mock.calls.map(([input]) => input.path)).toEqual([
    "/api/v1/notifications/devices",
    "/api/v1/notifications/devices/current",
    "/api/v1/notifications/preferences",
    "/api/v1/notifications/preferences",
    "/api/v1/notifications/devices/device%2F1",
  ]);
  expect(request.mock.calls.map(([input]) => input.method)).toEqual([
    "GET",
    "PUT",
    "GET",
    "PUT",
    "DELETE",
  ]);
  expect(request.mock.calls[1][0].body).toEqual({ provider: "fcm", token: "fcm-token" });
});
