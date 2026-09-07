import { Stack } from "expo-router";

import { RouteGuard } from "../../ui/navigation/RouteGuards";

export default function PhysicianLayout() {
  return (
    <RouteGuard kind="physician">
      <Stack screenOptions={{ headerShown: false }} />
    </RouteGuard>
  );
}
