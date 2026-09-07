import { Tabs } from "expo-router";

import { fiticianTokens } from "../../../../ui/tokens";

export default function MemberTabsLayout() {
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
      <Tabs.Screen name="workouts" options={{ tabBarLabel: "تمرین", title: "تمرین" }} />
      <Tabs.Screen name="nutrition" options={{ tabBarLabel: "تغذیه", title: "تغذیه" }} />
      <Tabs.Screen name="profile" options={{ tabBarLabel: "پروفایل", title: "پروفایل" }} />
    </Tabs>
  );
}
