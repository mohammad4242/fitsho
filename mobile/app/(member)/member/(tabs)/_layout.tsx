import { Tabs } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { AppIcon } from "../../../../ui/components";
import { fiticianTokens } from "../../../../ui/tokens";
import { decideMobileRoute, type MobileRouteSnapshot } from "../../../../ui/navigation/routePolicy";
import { useMobileRouteSnapshot } from "../../../../ui/navigation/RouteGuards";

export default function MemberTabsLayout() {
  const insets = useSafeAreaInsets();
  const snapshot = useMobileRouteSnapshot();
  const showTraining = canAccess(snapshot, "training");
  const showNutrition = canAccess(snapshot, "nutrition");

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: fiticianTokens.colors.aqua,
        tabBarHideOnKeyboard: true,
        tabBarInactiveTintColor: fiticianTokens.colors.muted,
        tabBarItemStyle: {
          minHeight: fiticianTokens.layout.minimumTouchTarget,
        },
        tabBarLabelPosition: "below-icon",
        tabBarLabelStyle: {
          fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
          fontSize: fiticianTokens.typography.fontSize.compact,
          lineHeight: 18,
        },
        tabBarStyle: {
          backgroundColor: fiticianTokens.colors.surfaceTranslucent,
          borderTopColor: fiticianTokens.colors.line,
          borderTopWidth: 1,
          height: 64 + Math.max(insets.bottom, 8),
          paddingBottom: Math.max(insets.bottom, 8),
          paddingTop: 8,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          tabBarIcon: ({ color, focused }) => (
            <AppIcon color={color} name="home" size={focused ? fiticianTokens.iconSize.lg : fiticianTokens.iconSize.md} />
          ),
          tabBarLabel: "خانه",
          title: "خانه",
        }}
      />
      <Tabs.Screen
        name="workouts"
        options={{
          href: showTraining ? undefined : null,
          tabBarIcon: ({ color, focused }) => (
            <AppIcon color={color} name="training" size={focused ? fiticianTokens.iconSize.lg : fiticianTokens.iconSize.md} />
          ),
          tabBarLabel: "تمرین",
          title: "تمرین",
        }}
      />
      <Tabs.Screen
        name="nutrition"
        options={{
          href: showNutrition ? undefined : null,
          tabBarIcon: ({ color, focused }) => (
            <AppIcon color={color} name="nutrition" size={focused ? fiticianTokens.iconSize.lg : fiticianTokens.iconSize.md} />
          ),
          tabBarLabel: "تغذیه",
          title: "تغذیه",
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          tabBarIcon: ({ color, focused }) => (
            <AppIcon color={color} name="profile" size={focused ? fiticianTokens.iconSize.lg : fiticianTokens.iconSize.md} />
          ),
          tabBarLabel: "پروفایل",
          title: "پروفایل",
        }}
      />
    </Tabs>
  );
}

function canAccess(snapshot: MobileRouteSnapshot, capability: "training" | "nutrition"): boolean {
  return decideMobileRoute("member", snapshot, capability).status === "allow";
}
