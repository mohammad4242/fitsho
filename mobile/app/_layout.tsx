import { useEffect } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";

import { createMobileQueryClient } from "../data/queryClient";
import { connectivityMonitor } from "../platform/connectivity";
import { MobileRouteStateProvider } from "../ui/navigation/RouteGuards";
import "../platform/backgroundSync";

const queryClient = createMobileQueryClient();

export default function RootLayout() {
  useEffect(() => {
    connectivityMonitor.start();
    return () => connectivityMonitor.stop();
  }, []);

  return (
    <MobileRouteStateProvider>
      <QueryClientProvider client={queryClient}>
        <Stack screenOptions={{ headerShown: false }} />
      </QueryClientProvider>
    </MobileRouteStateProvider>
  );
}
