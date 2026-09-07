import { Stack } from "expo-router";

import { RouteGuard } from "../../ui/navigation/RouteGuards";

export default function PublicLayout() {
  return (
    <RouteGuard kind="public">
      <Stack screenOptions={{ headerShown: false }} />
    </RouteGuard>
  );
}
