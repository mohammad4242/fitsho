import type { BottomTabBarProps } from "expo-router/build/react-navigation/bottom-tabs";
import { type ReactNode, useContext, useEffect } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  View,
  type ColorValue,
  type LayoutChangeEvent,
} from "react-native";
import { Circle, Path, Svg } from "react-native-svg";

import { BottomTabBarHeightCallbackContext } from "expo-router/build/react-navigation/bottom-tabs";
import { useIsKeyboardShown } from "expo-router/build/react-navigation/bottom-tabs/utils/useIsKeyboardShown";

import { fiticianTokens } from "../tokens";

const NAVIGATION_CONTENT_HEIGHT = 72;

type NavigationIconName = "home" | "dumbbell" | "nutrition" | "progress" | "more";

const iconPaths: Record<NavigationIconName, ReactNode> = {
  home: (
    <>
      <Path d="m3 10 9-7 9 7" />
      <Path d="M5 9v11h14V9M9 20v-6h6v6" />
    </>
  ),
  dumbbell: (
    <>
      <Path d="M7 8v8M4.5 9.5v5M2.5 11v2M17 8v8M19.5 9.5v5M21.5 11v2M7 12h10" />
    </>
  ),
  nutrition: (
    <>
      <Path d="M12 21c5-3 7-7 7-11a7 7 0 0 0-14 0c0 4 2 8 7 11Z" />
      <Path d="M8 12c3 0 5-2 5-5M12 21V11" />
    </>
  ),
  progress: (
    <>
      <Path d="M4 19V5M4 19h16" />
      <Path d="m7 15 4-4 3 2 5-6" />
    </>
  ),
  more: (
    <>
      <Circle cx="5" cy="12" r="1" />
      <Circle cx="12" cy="12" r="1" />
      <Circle cx="19" cy="12" r="1" />
    </>
  ),
};

const iconByRoute: Record<string, NavigationIconName> = {
  index: "home",
  workouts: "dumbbell",
  nutrition: "nutrition",
  "body-analysis": "progress",
  more: "more",
};

export function MemberBottomTabBar({ state, descriptors, navigation, insets }: BottomTabBarProps) {
  const onHeightChange = useContext(BottomTabBarHeightCallbackContext);
  const isKeyboardShown = useIsKeyboardShown();
  const focusedRouteKey = state.routes[state.index]?.key;
  const focusedOptions = focusedRouteKey === undefined
    ? undefined
    : descriptors[focusedRouteKey]?.options;
  const hiddenForKeyboard = focusedOptions?.tabBarHideOnKeyboard === true && isKeyboardShown;
  const visibleRoutes = state.routes.filter((route) => {
    const descriptor = descriptors[route.key];
    if (descriptor === undefined || iconByRoute[route.name] === undefined) {
      return false;
    }
    return StyleSheet.flatten(descriptor.options.tabBarItemStyle)?.display !== "none";
  });

  const handleLayout = (event: LayoutChangeEvent) => {
    onHeightChange?.(event.nativeEvent.layout.height);
  };

  useEffect(() => {
    onHeightChange?.(
      hiddenForKeyboard
        ? 0
        : NAVIGATION_CONTENT_HEIGHT + 1 + Math.max(insets.bottom, 0),
    );
  }, [hiddenForKeyboard, insets.bottom, onHeightChange]);

  if (hiddenForKeyboard) {
    return null;
  }

  return (
    <View
      accessibilityLabel="ناوبری اصلی"
      onLayout={handleLayout}
      style={[
        styles.bar,
        {
          paddingBottom: Math.max(insets.bottom, 0),
          paddingLeft: Math.max(insets.left, 0),
          paddingRight: Math.max(insets.right, 0),
        },
      ]}
      testID="member-bottom-tab-bar"
    >
      <View style={styles.content}>
        {visibleRoutes.map((route) => {
          const descriptor = descriptors[route.key];
          const iconName = iconByRoute[route.name];
          if (descriptor === undefined || iconName === undefined) {
            return null;
          }

          const focused = route.key === focusedRouteKey;
          const label = getTabLabel(descriptor.options, route.name, focused);
          const color = focused ? fiticianTokens.colors.aqua : fiticianTokens.colors.muted;
          const isEnglish = route.name === "body-analysis";

          const onPress = () => {
            const event = navigation.emit({
              type: "tabPress",
              target: route.key,
              canPreventDefault: true,
            });

            if (!focused && !event.defaultPrevented) {
              navigation.navigate(route.name, route.params);
            }
          };

          const onLongPress = () => {
            navigation.emit({
              type: "tabLongPress",
              target: route.key,
            });
          };

          return (
            <Pressable
              accessibilityLabel={descriptor.options.tabBarAccessibilityLabel ?? label}
              accessibilityRole="button"
              accessibilityState={{ selected: focused }}
              key={route.key}
              onLongPress={onLongPress}
              onPress={onPress}
              style={({ pressed }) => [
                styles.tab,
                focused && styles.activeTab,
                pressed && styles.pressedTab,
              ]}
              testID={descriptor.options.tabBarButtonTestID}
            >
              <MemberNavigationIcon color={color} name={iconName} />
              <Text
                adjustsFontSizeToFit
                allowFontScaling={descriptor.options.tabBarAllowFontScaling ?? true}
                minimumFontScale={0.72}
                numberOfLines={1}
                style={[
                  styles.label,
                  { color },
                  isEnglish ? styles.englishLabel : styles.persianLabel,
                  focused && styles.activeLabel,
                ]}
              >
                {label}
              </Text>
              {focused ? <View pointerEvents="none" style={styles.activeIndicator} /> : null}
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

function getTabLabel(
  options: BottomTabBarProps["descriptors"][string]["options"],
  routeName: string,
  focused: boolean,
): string {
  const label = typeof options.tabBarLabel === "function"
    ? options.tabBarLabel({
      children: options.title ?? routeName,
      color: focused ? fiticianTokens.colors.aqua : fiticianTokens.colors.muted,
      focused,
      position: "below-icon",
    })
    : options.tabBarLabel;

  return typeof label === "string" ? label : options.title ?? routeName;
}

type MemberNavigationIconProps = {
  readonly color: ColorValue;
  readonly name: NavigationIconName;
};

function MemberNavigationIcon({ color, name }: MemberNavigationIconProps) {
  const size = name === "dumbbell" ? 27 : 25;
  return (
    <Svg
      fill="none"
      height={size}
      stroke={color}
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={name === "dumbbell" ? 1.9 : 1.8}
      viewBox="0 0 24 24"
      width={size}
    >
      {iconPaths[name]}
    </Svg>
  );
}

const styles = StyleSheet.create({
  bar: {
    backgroundColor: fiticianTokens.colors.canvas,
    borderTopColor: fiticianTokens.colors.line,
    borderTopWidth: 1,
    width: "100%",
  },
  content: {
    flexDirection: "row",
    height: NAVIGATION_CONTENT_HEIGHT,
    paddingHorizontal: 4,
  },
  tab: {
    alignItems: "center",
    borderRadius: 11,
    flex: 1,
    justifyContent: "center",
    marginHorizontal: 2,
    marginVertical: 4,
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    minWidth: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: 2,
    paddingVertical: 4,
    position: "relative",
  },
  activeTab: {
    backgroundColor: fiticianTokens.colors.aquaAtmosphere,
  },
  pressedTab: {
    opacity: 0.82,
  },
  label: {
    fontSize: 13,
    fontWeight: fiticianTokens.typography.fontWeight.medium,
    includeFontPadding: false,
    lineHeight: 16,
    maxWidth: "100%",
    textAlign: "center",
  },
  persianLabel: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    writingDirection: "rtl",
  },
  englishLabel: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: 11,
    letterSpacing: -0.2,
    writingDirection: "ltr",
  },
  activeLabel: {
    color: fiticianTokens.colors.aqua,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
  },
  activeIndicator: {
    alignSelf: "center",
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    bottom: -4,
    height: 4,
    position: "absolute",
    width: 34,
  },
});
