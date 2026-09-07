import { QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";

import { createMobileQueryClient } from "../data/queryClient";

const queryClient = createMobileQueryClient();

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <Stack screenOptions={{ headerShown: false }} />
    </QueryClientProvider>
  );
}
