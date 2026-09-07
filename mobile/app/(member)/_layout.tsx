import { Stack } from "expo-router";

import { RouteGuard } from "../../ui/navigation/RouteGuards";

export default function MemberLayout() {
  return (
    <RouteGuard kind="member">
      <Stack screenOptions={{ headerShown: false }} />
    </RouteGuard>
  );
}
