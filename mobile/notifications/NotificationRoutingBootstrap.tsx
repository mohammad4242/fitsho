import { useCallback, useEffect, useRef, useState } from "react";
import * as Notifications from "expo-notifications";
import { useRouter } from "expo-router";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import {
  notificationPathFromResponse,
  type NotificationRoutePath,
} from "./notificationRouting";
import { securePendingNotificationRouteStore } from "./pendingNotificationRouteStore";

export function NotificationRoutingBootstrap() {
  const auth = useMobileAuth();
  const router = useRouter();
  const [pendingRoute, setPendingRoute] = useState<NotificationRoutePath | null>(null);
  const signInRequestedFor = useRef<NotificationRoutePath | null>(null);
  const handledResponseIds = useRef(new Set<string>());

  const acceptResponse = useCallback((response: Notifications.NotificationResponse) => {
    const responseId = response.notification.request.identifier;
    if (handledResponseIds.current.has(responseId)) return;
    handledResponseIds.current.add(responseId);
    const path = notificationPathFromResponse(response);
    if (path !== null) setPendingRoute(path);
  }, []);

  useEffect(() => {
    let active = true;
    const subscription = Notifications.addNotificationResponseReceivedListener(acceptResponse);
    void (async () => {
      const storedPath = await securePendingNotificationRouteStore.read().catch(() => null);
      if (active && storedPath !== null) setPendingRoute(storedPath);
      const lastResponse = await Notifications.getLastNotificationResponseAsync().catch(() => null);
      if (active && lastResponse !== null) acceptResponse(lastResponse);
    })();
    return () => {
      active = false;
      subscription.remove();
    };
  }, [acceptResponse]);

  useEffect(() => {
    if (pendingRoute === null || auth.status === "loading") return;
    if (auth.status !== "signed_in") {
      if (signInRequestedFor.current === pendingRoute) return;
      signInRequestedFor.current = pendingRoute;
      void securePendingNotificationRouteStore.write(pendingRoute);
      router.replace(auth.sessionExpired ? "/auth/sign-in?reason=session-expired" : "/auth/sign-in");
      return;
    }

    signInRequestedFor.current = null;
    setPendingRoute(null);
    void securePendingNotificationRouteStore.clear();
    router.replace(pendingRoute);
  }, [auth.sessionExpired, auth.status, pendingRoute, router]);

  return null;
}
