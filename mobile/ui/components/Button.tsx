import { type ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  type PressableProps,
  type PressableStateCallbackType,
  type StyleProp,
  type TextStyle,
  type ViewStyle,
} from "react-native";

import { fiticianTokens } from "../tokens";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export type ButtonProps = Omit<
  PressableProps,
  "accessibilityRole" | "accessibilityState" | "children" | "disabled" | "style"
> & {
  readonly accessibilityState?: PressableProps["accessibilityState"];
  readonly children?: ReactNode;
  readonly disabled?: boolean;
  readonly label?: string;
  readonly loading?: boolean;
  readonly style?: PressableProps["style"];
  readonly variant?: ButtonVariant;
};

const variantStyles: Record<ButtonVariant, ViewStyle> = {
  danger: {
    backgroundColor: fiticianTokens.colors.danger,
  },
  ghost: {
    backgroundColor: "transparent",
    borderColor: fiticianTokens.colors.line,
    borderWidth: 1,
  },
  primary: {
    backgroundColor: fiticianTokens.colors.aqua,
  },
  secondary: {
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderColor: fiticianTokens.colors.lineStrong,
    borderWidth: 1,
  },
};

const variantTextStyles: Record<ButtonVariant, TextStyle> = {
  danger: {
    color: fiticianTokens.colors.canvas,
  },
  ghost: {
    color: fiticianTokens.colors.mist,
  },
  primary: {
    color: fiticianTokens.colors.canvas,
  },
  secondary: {
    color: fiticianTokens.colors.mist,
  },
};

function resolvePressableStyle(
  style: ButtonProps["style"],
  pressed: boolean,
): StyleProp<ViewStyle> {
  return typeof style === "function" ? style({ pressed } as PressableStateCallbackType) : style;
}

export function Button({
  accessibilityState,
  children,
  disabled = false,
  label,
  loading = false,
  style,
  variant = "primary",
  ...pressableProps
}: ButtonProps) {
  const unavailable = disabled || loading;
  const text = children ?? label;
  const indicatorColor = variant === "secondary" || variant === "ghost"
    ? fiticianTokens.colors.aqua
    : fiticianTokens.colors.canvas;

  return (
    <Pressable
      {...pressableProps}
      accessibilityRole="button"
      accessibilityState={{ ...accessibilityState, busy: loading, disabled: unavailable }}
      disabled={unavailable}
      style={({ pressed }) => [
        styles.base,
        variantStyles[variant],
        pressed && !unavailable && styles.pressed,
        unavailable && styles.disabled,
        resolvePressableStyle(style, pressed),
      ]}
    >
      {loading ? (
        <ActivityIndicator accessibilityLabel="Loading" color={indicatorColor} size="small" />
      ) : (
        <Text style={[styles.label, variantTextStyles[variant]]}>{text}</Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    alignItems: "center",
    borderRadius: fiticianTokens.radii.medium,
    flexDirection: "row",
    justifyContent: "center",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    minWidth: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[4],
    paddingVertical: fiticianTokens.spacing[3],
  },
  disabled: {
    opacity: 0.48,
  },
  label: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 24,
    textAlign: "center",
    writingDirection: "rtl",
  },
  pressed: {
    opacity: 0.86,
    transform: [{ scale: fiticianTokens.motion.pressedScale }],
  },
});
