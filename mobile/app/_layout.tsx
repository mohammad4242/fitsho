import { useEffect } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { createMobileQueryClient } from "../data/queryClient";
import { MobileQueryCacheBoundary } from "../data/MobileQueryCacheBoundary";
import { MobileAuthProvider } from "../auth/MobileAuthProvider";
import { connectivityMonitor } from "../platform/connectivity";
import { MobileRouteStateProviderFromAuth } from "../ui/navigation/RouteGuards";
import { AndroidBackBehaviorProvider } from "../ui/navigation/BackBehaviorProvider";
import { configureFiticianRtl } from "../ui/rtl";
import "../platform/backgroundSync";

const queryClient = createMobileQueryClient();
configureFiticianRtl();

export default function RootLayout() {
  useEffect(() => {
    connectivityMonitor.start();
    return () => connectivityMonitor.stop();
  }, []);

  return (
    <SafeAreaProvider>
      <MobileAuthProvider>
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
