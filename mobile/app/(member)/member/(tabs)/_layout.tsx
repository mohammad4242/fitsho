import { Tabs } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { MemberBottomTabBar } from "../../../../ui/navigation/MemberBottomTabBar";
import { decideMobileRoute, type MobileRouteSnapshot } from "../../../../ui/navigation/routePolicy";
import { useMobileRouteSnapshot } from "../../../../ui/navigation/RouteGuards";

export default function MemberTabsLayout() {
  const insets = useSafeAreaInsets();
  const snapshot = useMobileRouteSnapshot();
  const showTraining = canAccess(snapshot, "training");
  const showNutrition = canAccess(snapshot, "nutrition");

  return (
    <Tabs
      safeAreaInsets={insets}
      tabBar={(props) => <MemberBottomTabBar {...props} />}
      screenOptions={{
        headerShown: false,
        tabBarHideOnKeyboard: true,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          tabBarLabel: "امروز",
          title: "امروز",
        }}
      />
      <Tabs.Screen
        name="workouts"
        options={{
          href: showTraining ? undefined : null,
          tabBarLabel: "تمرین",
          title: "تمرین",
        }}
      />
      <Tabs.Screen
        name="nutrition"
        options={{
          href: showNutrition ? undefined : null,
          tabBarLabel: "تغذیه",
          title: "تغذیه",
        }}
      />
      <Tabs.Screen
        name="body-analysis"
        options={{
          href: showTraining ? undefined : null,
          tabBarLabel: "Body Analysis",
          title: "Body Analysis",
        }}
      />
      <Tabs.Screen
        name="more"
        options={{
          tabBarLabel: "بیشتر",
          title: "بیشتر",
        }}
      />
    </Tabs>
  );
}

function canAccess(snapshot: MobileRouteSnapshot, capability: "training" | "nutrition"): boolean {
  return decideMobileRoute("member", snapshot, capability).status === "allow";
}
