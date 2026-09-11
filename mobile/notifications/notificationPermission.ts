import * as Notifications from "expo-notifications";
import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

export const NOTIFICATION_PERMISSION_REQUESTED_KEY = "fitician.notifications.permission-requested";

export type NotificationPermissionStatus =
  | "blocked"
  | "denied"
  | "granted"
  | "not_required"
  | "not_supported";

export type NotificationProvider = "fcm" | "apns";

export interface NativePushToken {
  readonly provider: NotificationProvider;
  readonly token: string;
}

export interface NotificationPermissionRequestStore {
  read(): Promise<string | null>;
  write(value: string): Promise<void>;
}

function notificationPermissionIsUsable(
  permissions: Notifications.NotificationPermissionsStatus,
): boolean {
  if (permissions.granted) return true;
  if (Platform.OS !== "ios") return false;
  return permissions.ios?.status === Notifications.IosAuthorizationStatus.PROVISIONAL
    || permissions.ios?.status === Notifications.IosAuthorizationStatus.EPHEMERAL;
}

const securePermissionRequestStore: NotificationPermissionRequestStore = {
  read: () => SecureStore.getItemAsync(NOTIFICATION_PERMISSION_REQUESTED_KEY),
  write: (value) => SecureStore.setItemAsync(NOTIFICATION_PERMISSION_REQUESTED_KEY, value),
};

export const ANDROID_NOTIFICATION_CHANNELS: ReadonlyArray<{
  readonly id: string;
  readonly configuration: Notifications.NotificationChannelInput;
}> = [
  {
    id: "fitician-activity",
    configuration: {
      name: "فعالیت‌های فیتیچیان",
      description: "به‌روزرسانی‌های برنامه تمرینی و تغذیه‌ای",
      importance: Notifications.AndroidImportance.DEFAULT,
      lockscreenVisibility: Notifications.AndroidNotificationVisibility.PRIVATE,
      showBadge: true,
      vibrationPattern: [0, 250, 250, 250],
      enableLights: true,
      enableVibrate: true,
      lightColor: "#7C5CFC",
    },
  },
  {
    id: "fitician-reminders",
    configuration: {
      name: "یادآوری‌های فیتیچیان",
      description: "یادآوری‌های چرخه و بررسی‌های برنامه",
      importance: Notifications.AndroidImportance.DEFAULT,
      lockscreenVisibility: Notifications.AndroidNotificationVisibility.PRIVATE,
      showBadge: true,
      vibrationPattern: [0, 250, 250, 250],
      enableLights: true,
      enableVibrate: true,
      lightColor: "#49D3A4",
    },
  },
  {
    id: "fitician-health",
    configuration: {
      name: "به‌روزرسانی‌های سلامت",
      description: "نتیجه‌های تحلیل بدن و تصمیم‌های بالینی",
      importance: Notifications.AndroidImportance.DEFAULT,
      lockscreenVisibility: Notifications.AndroidNotificationVisibility.PRIVATE,
      showBadge: true,
      vibrationPattern: [0, 250, 250, 250],
      enableLights: true,
      enableVibrate: true,
      lightColor: "#FFB86B",
    },
  },
];

export function androidApiLevel(version: unknown): number | null {
  if (typeof version === "number" && Number.isFinite(version)) {
    return Math.trunc(version);
  }
  if (typeof version === "string" && /^\d+$/.test(version)) {
    return Number.parseInt(version, 10);
  }
  return null;
}

export function androidNotificationPermissionRequired(
  version: unknown = Platform.Version,
): boolean {
  const apiLevel = androidApiLevel(version);
  return Platform.OS === "android" && apiLevel !== null && apiLevel >= 33;
}

export async function configureAndroidNotificationChannels(): Promise<void> {
  const apiLevel = androidApiLevel(Platform.Version);
  if (Platform.OS !== "android" || (apiLevel !== null && apiLevel < 26)) {
    return;
  }
  for (const channel of ANDROID_NOTIFICATION_CHANNELS) {
    await Notifications.setNotificationChannelAsync(channel.id, channel.configuration);
  }
}

export async function requestAndroidNotificationPermission(
  storage: NotificationPermissionRequestStore = securePermissionRequestStore,
): Promise<NotificationPermissionStatus> {
  if (Platform.OS !== "android") {
    return "not_supported";
  }
  if (!androidNotificationPermissionRequired()) {
    return "not_required";
  }

  const current = await Notifications.getPermissionsAsync();
  if (notificationPermissionIsUsable(current)) {
    return "granted";
  }
  if (!current.canAskAgain) {
    return "blocked";
  }
  if ((await storage.read()) === "1") {
    return "denied";
  }

  const requested = await Notifications.requestPermissionsAsync();
  await storage.write("1");
  if (notificationPermissionIsUsable(requested)) {
    return "granted";
  }
  return requested.canAskAgain ? "denied" : "blocked";
}

export async function prepareAndroidNotifications(
  storage: NotificationPermissionRequestStore = securePermissionRequestStore,
): Promise<NotificationPermissionStatus> {
  await configureAndroidNotificationChannels();
  return requestAndroidNotificationPermission(storage);
}

export async function requestNotificationPermission(
  storage: NotificationPermissionRequestStore = securePermissionRequestStore,
): Promise<NotificationPermissionStatus> {
  if (Platform.OS !== "android" && Platform.OS !== "ios") {
    return "not_supported";
  }
  if (Platform.OS === "android" && !androidNotificationPermissionRequired()) {
    return "not_required";
  }

  const current = await Notifications.getPermissionsAsync();
  if (notificationPermissionIsUsable(current)) {
    return "granted";
  }
  if (!current.canAskAgain) {
    return "blocked";
  }
  if ((await storage.read()) === "1") {
    return "denied";
  }

  const requested = await Notifications.requestPermissionsAsync();
  await storage.write("1");
  if (notificationPermissionIsUsable(requested)) {
    return "granted";
  }
  return requested.canAskAgain ? "denied" : "blocked";
}

export async function prepareNotifications(
  storage: NotificationPermissionRequestStore = securePermissionRequestStore,
): Promise<NotificationPermissionStatus> {
  await configureAndroidNotificationChannels();
  return requestNotificationPermission(storage);
}

export async function getNativePushToken(): Promise<NativePushToken | null> {
  if (Platform.OS !== "android" && Platform.OS !== "ios") {
    return null;
  }
  return nativePushTokenFromDevicePushToken(await Notifications.getDevicePushTokenAsync());
}

export function nativePushTokenFromDevicePushToken(
  token: Notifications.DevicePushToken,
): NativePushToken | null {
  if (Platform.OS !== "android" && Platform.OS !== "ios") {
    return null;
  }
  const expectedType = Platform.OS;
  if (token.type !== expectedType || typeof token.data !== "string" || !token.data.trim()) {
    return null;
  }
  return {
    provider: expectedType === "ios" ? "apns" : "fcm",
    token: token.data,
  };
}

export async function getAndroidFcmToken(): Promise<string | null> {
  const token = await getNativePushToken();
  return token?.provider === "fcm" ? token.token : null;
}

export async function getIosApnsToken(): Promise<string | null> {
  const token = await getNativePushToken();
  return token?.provider === "apns" ? token.token : null;
}
