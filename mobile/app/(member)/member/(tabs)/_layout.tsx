import { Tabs } from "expo-router";

import { fiticianTokens } from "../../../../ui/tokens";
import { decideMobileRoute, type MobileRouteSnapshot } from "../../../../ui/navigation/routePolicy";
import { useMobileRouteSnapshot } from "../../../../ui/navigation/RouteGuards";

export default function MemberTabsLayout() {
  const snapshot = useMobileRouteSnapshot();
  const showTraining = canAccess(snapshot, "training");
  const showNutrition = canAccess(snapshot, "nutrition");

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: fiticianTokens.colors.aqua,
        tabBarInactiveTintColor: fiticianTokens.colors.muted,
        tabBarLabelStyle: {
          fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
          fontSize: fiticianTokens.typography.fontSize.xs,
        },
        tabBarStyle: {
          backgroundColor: fiticianTokens.colors.surface,
          borderTopColor: fiticianTokens.colors.line,
          height: 64,
        },
      }}
    >
      <Tabs.Screen name="index" options={{ tabBarLabel: "خانه", title: "خانه" }} />
      <Tabs.Screen
        name="workouts"
        options={{ href: showTraining ? undefined : null, tabBarLabel: "تمرین", title: "تمرین" }}
      />
      <Tabs.Screen
        name="nutrition"
        options={{ href: showNutrition ? undefined : null, tabBarLabel: "تغذیه", title: "تغذیه" }}
      />
      <Tabs.Screen name="profile" options={{ tabBarLabel: "پروفایل", title: "پروفایل" }} />
    </Tabs>
  );
}

function canAccess(snapshot: MobileRouteSnapshot, capability: "training" | "nutrition"): boolean {
  return decideMobileRoute("member", snapshot, capability).status === "allow";
}
