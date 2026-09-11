import { afterEach, expect, it, vi } from "vitest";

const platform = vi.hoisted(() => ({ OS: "android", Version: 35 }));
const mocks = vi.hoisted(() => ({
  getDevicePushTokenAsync: vi.fn(),
  getItemAsync: vi.fn(),
  getPermissionsAsync: vi.fn(),
  requestPermissionsAsync: vi.fn(),
  setItemAsync: vi.fn(),
  setNotificationChannelAsync: vi.fn(),
}));

vi.mock("react-native", () => ({ Platform: platform }));
vi.mock("expo-notifications", () => ({
  AndroidImportance: { DEFAULT: 5, HIGH: 6 },
  AndroidNotificationVisibility: { PRIVATE: 2 },
  IosAuthorizationStatus: { EPHEMERAL: 4, PROVISIONAL: 3 },
  getDevicePushTokenAsync: mocks.getDevicePushTokenAsync,
  getPermissionsAsync: mocks.getPermissionsAsync,
  requestPermissionsAsync: mocks.requestPermissionsAsync,
  setNotificationChannelAsync: mocks.setNotificationChannelAsync,
}));
vi.mock("expo-secure-store", () => ({
  getItemAsync: mocks.getItemAsync,
  setItemAsync: mocks.setItemAsync,
}));

import * as Notifications from "expo-notifications";

import {
  configureAndroidNotificationChannels,
  getIosApnsToken,
  getAndroidFcmToken,
  getNativePushToken,
  NOTIFICATION_PERMISSION_REQUESTED_KEY,
  prepareNotifications,
  requestAndroidNotificationPermission,
  type NotificationPermissionRequestStore,
} from "./notificationPermission";

const store: NotificationPermissionRequestStore = {
  read: async () => null,
  write: async () => undefined,
};

afterEach(() => {
  platform.OS = "android";
  platform.Version = 35;
  vi.clearAllMocks();
});

it("creates private Android channels for activity, reminders, and health updates", async () => {
  await configureAndroidNotificationChannels();

  expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledTimes(3);
  expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledWith(
    "fitician-activity",
    expect.objectContaining({
      lockscreenVisibility: 2,
      name: "فعالیت‌های فیتیچیان",
    }),
  );
  expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledWith(
    "fitician-reminders",
    expect.objectContaining({ name: "یادآوری‌های فیتیچیان" }),
  );
  expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledWith(
    "fitician-health",
    expect.objectContaining({ name: "به‌روزرسانی‌های سلامت" }),
  );
  for (const [, configuration] of mocks.setNotificationChannelAsync.mock.calls) {
    expect(configuration).not.toHaveProperty("sound");
  }
});

it("requests Android 13 notification permission once and classifies the result", async () => {
  mocks.getItemAsync.mockResolvedValue(null);
  mocks.getPermissionsAsync.mockResolvedValue({ granted: false, canAskAgain: true });
  mocks.requestPermissionsAsync.mockResolvedValue({ granted: true, canAskAgain: true });

  const permission = await requestAndroidNotificationPermission(store);

  expect(permission).toBe("granted");
  expect(mocks.requestPermissionsAsync).toHaveBeenCalledOnce();
  expect(NOTIFICATION_PERMISSION_REQUESTED_KEY).toBe("fitician.notifications.permission-requested");
});

it("does not prompt again after a recorded denial or when the system blocks prompts", async () => {
  const deniedStore: NotificationPermissionRequestStore = {
    read: async () => "1",
    write: async () => undefined,
  };
  mocks.getPermissionsAsync.mockResolvedValue({ granted: false, canAskAgain: true });
  await expect(requestAndroidNotificationPermission(deniedStore)).resolves.toBe("denied");
  expect(mocks.requestPermissionsAsync).not.toHaveBeenCalled();

  mocks.getPermissionsAsync.mockResolvedValue({ granted: false, canAskAgain: false });
  await expect(requestAndroidNotificationPermission(store)).resolves.toBe("blocked");
  expect(mocks.requestPermissionsAsync).not.toHaveBeenCalled();
});

it("does not request permission on Android versions below 33 and returns the native FCM token", async () => {
  platform.Version = 32;
  await expect(requestAndroidNotificationPermission(store)).resolves.toBe("not_required");
  expect(mocks.getPermissionsAsync).not.toHaveBeenCalled();

  mocks.getDevicePushTokenAsync.mockResolvedValue({ type: "android", data: "fcm-token" });
  await expect(getAndroidFcmToken()).resolves.toBe("fcm-token");
});

it("requests iOS permission and returns the native APNs token without relabeling it", async () => {
  platform.OS = "ios";
  mocks.getPermissionsAsync.mockResolvedValue({ granted: false, canAskAgain: true });
  mocks.requestPermissionsAsync.mockResolvedValue({ granted: true, canAskAgain: true });
  mocks.getDevicePushTokenAsync.mockResolvedValue({ type: "ios", data: "apns-token" });

  await expect(prepareNotifications(store)).resolves.toBe("granted");
  await expect(getNativePushToken()).resolves.toEqual({
    provider: "apns",
    token: "apns-token",
  });
  await expect(getIosApnsToken()).resolves.toBe("apns-token");
  expect(mocks.setNotificationChannelAsync).not.toHaveBeenCalled();
});

it("treats provisional iOS notification permission as usable", async () => {
  platform.OS = "ios";
  mocks.getPermissionsAsync.mockResolvedValue({
    granted: false,
    canAskAgain: false,
    ios: { status: Notifications.IosAuthorizationStatus.PROVISIONAL },
  });

  await expect(prepareNotifications(store)).resolves.toBe("granted");
  expect(mocks.requestPermissionsAsync).not.toHaveBeenCalled();
});

it("classifies denied and blocked iOS notification permission", async () => {
  platform.OS = "ios";
  mocks.getPermissionsAsync.mockResolvedValue({ granted: false, canAskAgain: false });

  await expect(prepareNotifications(store)).resolves.toBe("blocked");
  expect(mocks.requestPermissionsAsync).not.toHaveBeenCalled();
});
