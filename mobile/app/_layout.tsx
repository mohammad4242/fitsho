import { useEffect, useMemo, useRef } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { Stack, usePathname } from "expo-router";
import { InteractionManager } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { createMobileQueryClient } from "../data/queryClient";
import { MobileQueryCacheBoundary } from "../data/MobileQueryCacheBoundary";
import { MobileAuthProvider, useMobileAuth } from "../auth/MobileAuthProvider";
import { logMobileRuntimeConfiguration } from "../config/nativeRuntimeConfig";
import { E2ERoleNavigator } from "../e2e/RoleNavigator";
import { connectivityMonitor } from "../platform/connectivity";
import {
  completeMobileColdStart,
  mobilePerformanceRecorder,
  type PerformanceMeasurement,
} from "../platform/performance";
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

function ScreenTransitionPerformanceBootstrap() {
  const pathname = usePathname();
  const previousPathname = useRef(pathname);
  const pendingMeasurement = useRef<(() => PerformanceMeasurement) | null>(null);

  useEffect(() => {
    if (previousPathname.current === pathname) {
      return undefined;
    }
    previousPathname.current = pathname;
    const complete = mobilePerformanceRecorder.start("screen_transition");
    pendingMeasurement.current = complete;
    const task = InteractionManager.runAfterInteractions(() => {
      if (pendingMeasurement.current === complete) {
        pendingMeasurement.current = null;
        complete();
      }
    });
    return () => {
      task.cancel();
      if (pendingMeasurement.current === complete) {
        pendingMeasurement.current = null;
        complete();
      }
    };
  }, [pathname]);

  return null;
}

export default function RootLayout() {
  useEffect(() => {
    completeMobileColdStart();
    logMobileRuntimeConfiguration();
    connectivityMonitor.start();
    return () => connectivityMonitor.stop();
  }, []);

  return (
    <SafeAreaProvider>
      <ScreenTransitionPerformanceBootstrap />
      <MobileAuthProvider>
        <E2ERoleNavigator />
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
