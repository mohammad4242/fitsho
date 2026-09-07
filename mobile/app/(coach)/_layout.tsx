import { Stack } from "expo-router";

import { RouteGuard } from "../../ui/navigation/RouteGuards";

export default function CoachLayout() {
  return (
    <RouteGuard kind="coach">
      <Stack screenOptions={{ headerShown: false }} />
    </RouteGuard>
  );
}
