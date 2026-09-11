import type {
  NativePushToken,
  NotificationPermissionStatus,
} from "./notificationPermission";

export type NotificationRegistrationResult =
  | "registered"
  | "permission_denied"
  | "token_unavailable";

export interface NotificationRegistrationDependencies {
  readonly prepare: () => Promise<NotificationPermissionStatus>;
  readonly getToken: () => Promise<NativePushToken | null>;
  readonly register: (token: NativePushToken) => Promise<void>;
}

export async function registerNotifications(
  dependencies: NotificationRegistrationDependencies,
): Promise<NotificationRegistrationResult> {
  const permission = await dependencies.prepare();
  if (permission !== "granted" && permission !== "not_required") {
    return "permission_denied";
  }
  const token = await dependencies.getToken();
  if (token === null) {
    return "token_unavailable";
  }
  await dependencies.register(token);
  return "registered";
}

export interface AndroidNotificationRegistrationDependencies {
  readonly prepare: () => Promise<NotificationPermissionStatus>;
  readonly getToken: () => Promise<string | null>;
  readonly register: (token: string) => Promise<void>;
}

export async function registerAndroidNotifications(
  dependencies: AndroidNotificationRegistrationDependencies,
): Promise<NotificationRegistrationResult> {
  return registerNotifications({
    prepare: dependencies.prepare,
    getToken: async () => {
      const token = await dependencies.getToken();
      return token === null ? null : { provider: "fcm", token };
    },
    register: ({ token }) => dependencies.register(token),
  });
}
