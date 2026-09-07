import * as SecureStore from "expo-secure-store";

import {
  isNotificationRoutePath,
  type NotificationRoutePath,
} from "./notificationRouting";

export const PENDING_NOTIFICATION_ROUTE_KEY = "fitician.notifications.pending-route";

export interface PendingNotificationRouteStore {
  read(): Promise<NotificationRoutePath | null>;
  write(path: NotificationRoutePath): Promise<void>;
  clear(): Promise<void>;
}

export const securePendingNotificationRouteStore: PendingNotificationRouteStore = {
  async read() {
    const value = await SecureStore.getItemAsync(PENDING_NOTIFICATION_ROUTE_KEY);
    return value !== null && isNotificationRoutePath(value) ? value : null;
  },
  async write(path) {
    if (!isNotificationRoutePath(path)) {
      throw new Error("Invalid pending notification route");
    }
    await SecureStore.setItemAsync(PENDING_NOTIFICATION_ROUTE_KEY, path);
  },
  clear: () => SecureStore.deleteItemAsync(PENDING_NOTIFICATION_ROUTE_KEY),
};
