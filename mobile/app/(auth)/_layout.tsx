import { Stack } from "expo-router";

import { RouteGuard } from "../../ui/navigation/RouteGuards";

export default function AuthLayout() {
  return (
    <RouteGuard kind="auth">
      <Stack screenOptions={{ headerShown: false }} />
    </RouteGuard>
  );
}
