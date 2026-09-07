import { useEffect, useMemo } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { createMobileQueryClient } from "../data/queryClient";
import { MobileQueryCacheBoundary } from "../data/MobileQueryCacheBoundary";
import { MobileAuthProvider, useMobileAuth } from "../auth/MobileAuthProvider";
import { connectivityMonitor } from "../platform/connectivity";
import {
  getAndroidFcmToken,
  prepareAndroidNotifications,
} from "../notifications/notificationPermission";
import { createNotificationApi } from "../notifications/notificationApi";
import { registerAndroidNotifications } from "../notifications/notificationRegistration";
import { configureNotificationRuntime } from "../notifications/notificationRuntime";
import { NotificationRoutingBootstrap } from "../notifications/NotificationRoutingBootstrap";
import { MobileRouteStateProviderFromAuth } from "../ui/navigation/RouteGuards";
import { AndroidBackBehaviorProvider } from "../ui/navigation/BackBehaviorProvider";
import { configureFiticianRtl } from "../ui/rtl";
import "../platform/backgroundSync";

const queryClient = createMobileQueryClient();
configureFiticianRtl();
configureNotificationRuntime();

function NotificationPermissionBootstrap() {
  const auth = useMobileAuth();
  const notificationApi = useMemo(() => createNotificationApi(auth.request), [auth.request]);

  useEffect(() => {
    if (auth.status !== "signed_in") {
      return;
    }
    void registerAndroidNotifications({
      prepare: prepareAndroidNotifications,
      getToken: getAndroidFcmToken,
      register: async (token) => {
        await notificationApi.registerCurrentDevice(token);
      },
    }).catch(() => undefined);
  }, [auth.status, notificationApi]);

  return null;
}

export default function RootLayout() {
  useEffect(() => {
    connectivityMonitor.start();
    return () => connectivityMonitor.stop();
  }, []);

  return (
    <SafeAreaProvider>
      <MobileAuthProvider>
        <NotificationPermissionBootstrap />
        <NotificationRoutingBootstrap />
        <MobileRouteStateProviderFromAuth>
          <AndroidBackBehaviorProvider>
            <QueryClientProvider client={queryClient}>
              <MobileQueryCacheBoundary>
                <Stack screenOptions={{ headerShown: false }} />
              </MobileQueryCacheBoundary>
            </QueryClientProvider>
          </AndroidBackBehaviorProvider>
        </MobileRouteStateProviderFromAuth>
      </MobileAuthProvider>
    </SafeAreaProvider>
  );
}
