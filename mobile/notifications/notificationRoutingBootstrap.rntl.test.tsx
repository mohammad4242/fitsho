import { act, render, waitFor } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";

jest.mock("expo-notifications", () => ({
  addNotificationResponseReceivedListener: jest.fn(),
  getLastNotificationResponseAsync: jest.fn(),
}));
jest.mock("expo-router", () => ({ useRouter: jest.fn() }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("./pendingNotificationRouteStore", () => ({
  securePendingNotificationRouteStore: {
    read: jest.fn(),
    write: jest.fn(),
    clear: jest.fn(),
  },
}));

import * as Notifications from "expo-notifications";
import { useRouter } from "expo-router";
import { useMobileAuth } from "../auth/MobileAuthProvider";
import { securePendingNotificationRouteStore } from "./pendingNotificationRouteStore";

import { NotificationRoutingBootstrap } from "./NotificationRoutingBootstrap";

const mockRouter = {
  replace: jest.fn(),
};

const addNotificationResponseReceivedListener = jest.mocked(
  Notifications.addNotificationResponseReceivedListener,
);
const getLastNotificationResponseAsync = jest.mocked(Notifications.getLastNotificationResponseAsync);
const readPendingRoute = jest.mocked(securePendingNotificationRouteStore.read);
const writePendingRoute = jest.mocked(securePendingNotificationRouteStore.write);
const clearPendingRoute = jest.mocked(securePendingNotificationRouteStore.clear);
const mockUseMobileAuthHook = jest.mocked(useMobileAuth);
const mockUseRouterHook = jest.mocked(useRouter);

function response(identifier: string, eventType: string) {
  return {
    notification: {
      request: {
        content: { data: { event_type: eventType } },
        identifier,
      },
    },
  };
}

beforeEach(() => {
  addNotificationResponseReceivedListener.mockReset();
  getLastNotificationResponseAsync.mockReset();
  readPendingRoute.mockReset();
  writePendingRoute.mockReset();
  clearPendingRoute.mockReset();
  mockUseMobileAuthHook.mockReset();
  mockUseRouterHook.mockReset();
  mockRouter.replace.mockReset();
  readPendingRoute.mockResolvedValue(null);
  getLastNotificationResponseAsync.mockResolvedValue(null);
  addNotificationResponseReceivedListener.mockReturnValue({ remove: jest.fn() });
  mockUseMobileAuthHook.mockReturnValue({ status: "signed_out", sessionExpired: false } as never);
  mockUseRouterHook.mockReturnValue(mockRouter as never);
});

test("holds a terminated notification route across sign-in and opens it after restore", async () => {
  getLastNotificationResponseAsync.mockResolvedValue(
    response("terminated-1", "workout_plan_approved") as never,
  );

  const view = render(<NotificationRoutingBootstrap />);

  await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith("/auth/sign-in"));
  expect(writePendingRoute).toHaveBeenCalledWith("/member/workouts");

  mockRouter.replace.mockReset();
  mockUseMobileAuthHook.mockReturnValue({ status: "signed_in", sessionExpired: false } as never);
  await act(async () => {
    view.rerender(<NotificationRoutingBootstrap />);
  });

  await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith("/member/workouts"));
  expect(clearPendingRoute).toHaveBeenCalledTimes(1);
});

test("routes a foreground response once and ignores duplicate delivery", async () => {
  const view = render(<NotificationRoutingBootstrap />);
  const listener = addNotificationResponseReceivedListener.mock.calls[0]?.[0] as
    | ((value: unknown) => void)
    | undefined;
  expect(listener).toBeDefined();
  if (listener === undefined) return;

  mockUseMobileAuthHook.mockReturnValue({ status: "signed_in", sessionExpired: false } as never);
  await act(async () => {
    listener(response("foreground-1", "nutrition_plan_approved"));
  });
  await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith("/member/nutrition"));

  await act(async () => {
    listener(response("foreground-1", "nutrition_plan_approved"));
  });
  expect(mockRouter.replace).toHaveBeenCalledTimes(1);
  view.unmount();
});
