import type { components, TransportRequest } from "@fitician/core";
import { Platform } from "react-native";

export type NotificationDevice = components["schemas"]["NotificationDeviceResponse"];
export type NotificationPreferences = components["schemas"]["NotificationPreferencesResponse"];
export type NotificationPreferencesUpdate = components["schemas"]["NotificationPreferencesUpdateRequest"];
export type NotificationTokenProvider = "fcm" | "apns";

export function notificationProviderForPlatform(platform: string): NotificationTokenProvider {
  return platform === "ios" ? "apns" : "fcm";
}

export type AuthenticatedNotificationRequest = <TResponse>(
  request: TransportRequest,
) => Promise<TResponse>;

export interface NotificationApi {
  getPreferences(): Promise<NotificationPreferences>;
  listDevices(): Promise<NotificationDevice[]>;
  registerCurrentDevice(token: string, provider?: NotificationTokenProvider): Promise<NotificationDevice>;
  unregisterDevice(deviceId: string): Promise<void>;
  updatePreferences(input: NotificationPreferencesUpdate): Promise<NotificationPreferences>;
}

function jsonBody(value: object): TransportRequest["body"] {
  return value as TransportRequest["body"];
}

export function createNotificationApi(
  request: AuthenticatedNotificationRequest,
): NotificationApi {
  return {
    getPreferences: () => request<NotificationPreferences>({
      method: "GET",
      path: "/api/v1/notifications/preferences",
    }),
    listDevices: () => request<NotificationDevice[]>({
      method: "GET",
      path: "/api/v1/notifications/devices",
    }),
    registerCurrentDevice: (token, provider = notificationProviderForPlatform(Platform.OS)) => request<NotificationDevice>({
      body: jsonBody({ provider, token }),
      method: "PUT",
      path: "/api/v1/notifications/devices/current",
    }),
    unregisterDevice: async (deviceId) => {
      await request<void>({
        method: "DELETE",
        path: `/api/v1/notifications/devices/${encodeURIComponent(deviceId)}`,
      });
    },
    updatePreferences: (input) => request<NotificationPreferences>({
      body: jsonBody(input),
      method: "PUT",
      path: "/api/v1/notifications/preferences",
    }),
  } satisfies NotificationApi;
}
