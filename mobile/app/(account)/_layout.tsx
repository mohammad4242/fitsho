import { Stack } from "expo-router";

import { RouteGuard } from "../../ui/navigation/RouteGuards";

export default function AccountLayout() {
  return (
    <RouteGuard kind="account">
      <Stack screenOptions={{ headerShown: false }} />
    </RouteGuard>
  );
}
