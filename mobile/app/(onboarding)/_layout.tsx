import { Stack } from "expo-router";

import { RouteGuard } from "../../ui/navigation/RouteGuards";

export default function OnboardingLayout() {
  return (
    <RouteGuard kind="onboarding">
      <Stack screenOptions={{ headerShown: false }} />
    </RouteGuard>
  );
}
