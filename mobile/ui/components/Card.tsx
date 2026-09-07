import {
  Pressable,
  StyleSheet,
  View,
  type PressableProps,
  type StyleProp,
  type ViewProps,
  type ViewStyle,
} from "react-native";
import { type ReactNode } from "react";

import { fiticianTokens } from "../tokens";

export type CardVariant = "default" | "raised" | "interactive";

export interface CardProps extends Omit<ViewProps, "style"> {
  readonly children: ReactNode;
  readonly onPress?: PressableProps["onPress"];
  readonly style?: StyleProp<ViewStyle>;
  readonly variant?: CardVariant;
}

const variantStyles: Record<CardVariant, ViewStyle> = {
  default: {
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
  },
  interactive: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
  },
  raised: {
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderColor: fiticianTokens.colors.line,
  },
};

export function Card({ children, onPress, style, variant = "default", ...viewProps }: CardProps) {
  const cardStyle = [styles.base, variantStyles[variant], style];

  if (!onPress) {
    return (
      <View {...viewProps} style={cardStyle}>
        {children}
      </View>
    );
  }

  return (
    <Pressable
      {...viewProps}
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [cardStyle, pressed && styles.pressed]}
    >
      {children}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    borderRadius: fiticianTokens.radii.card,
    borderWidth: 1,
    elevation: fiticianTokens.shadows.card.elevation,
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    padding: fiticianTokens.spacing[4],
    shadowColor: fiticianTokens.shadows.card.color,
    shadowOffset: fiticianTokens.shadows.card.offset,
    shadowOpacity: fiticianTokens.shadows.card.opacity,
    shadowRadius: fiticianTokens.shadows.card.radius,
  },
  pressed: {
    opacity: 0.88,
    transform: [{ scale: fiticianTokens.motion.pressedScale }],
  },
});
