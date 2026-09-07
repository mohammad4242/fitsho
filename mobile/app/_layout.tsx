import { useEffect } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";

import { createMobileQueryClient } from "../data/queryClient";
import { connectivityMonitor } from "../platform/connectivity";
import "../platform/backgroundSync";

const queryClient = createMobileQueryClient();

export default function RootLayout() {
  useEffect(() => {
    connectivityMonitor.start();
    return () => connectivityMonitor.stop();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <Stack screenOptions={{ headerShown: false }} />
    </QueryClientProvider>
  );
}
