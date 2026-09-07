import { expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ setNotificationHandler: vi.fn() }));

vi.mock("expo-notifications", () => mocks);

import * as Notifications from "expo-notifications";

import { configureNotificationRuntime } from "./notificationRuntime";

it("shows safe remote notifications while the app is in the foreground", async () => {
  configureNotificationRuntime();

  const handler = vi.mocked(Notifications.setNotificationHandler).mock.calls[0]?.[0];
  expect(handler).not.toBeNull();
  if (handler === undefined || handler === null) {
    return;
  }
  await expect(handler.handleNotification({} as Notifications.Notification)).resolves.toEqual({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  });
});
