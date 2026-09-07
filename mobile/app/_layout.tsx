import { useEffect } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { createMobileQueryClient } from "../data/queryClient";
import { connectivityMonitor } from "../platform/connectivity";
import { MobileRouteStateProvider } from "../ui/navigation/RouteGuards";
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
      <MobileRouteStateProvider>
        <QueryClientProvider client={queryClient}>
          <Stack screenOptions={{ headerShown: false }} />
        </QueryClientProvider>
      </MobileRouteStateProvider>
    </SafeAreaProvider>
  );
}
