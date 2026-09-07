import { type ReactNode } from "react";
import {
  StyleSheet,
  Text,
  View,
  type DimensionValue,
  type StyleProp,
  type ViewStyle,
} from "react-native";

import { fiticianTokens } from "../tokens";
import { Button } from "./Button";

export interface SkeletonProps {
  readonly accessibilityLabel?: string;
  readonly height?: DimensionValue;
  readonly radius?: number;
  readonly style?: StyleProp<ViewStyle>;
  readonly width?: DimensionValue;
}

export function Skeleton({
  accessibilityLabel = "Loading",
  height = fiticianTokens.spacing[4],
  radius = fiticianTokens.radii.small,
  style,
  width = "100%",
}: SkeletonProps) {
  return (
    <View
      accessible
      accessibilityLabel={accessibilityLabel}
      accessibilityRole="progressbar"
      style={[styles.skeleton, { borderRadius: radius, height, width }, style]}
    />
  );
}

export type NoticeVariant = "info" | "success" | "warning" | "danger" | "offline";

export interface NoticeProps {
  readonly actionLabel?: string;
  readonly message: string;
  readonly onAction?: () => void;
  readonly title?: string;
  readonly variant?: NoticeVariant;
}

const noticeStyles: Record<NoticeVariant, ViewStyle> = {
  danger: {
    backgroundColor: "rgba(246,120,89,0.12)",
    borderColor: fiticianTokens.colors.danger,
  },
  info: {
    backgroundColor: "rgba(80,223,206,0.08)",
    borderColor: fiticianTokens.colors.aqua,
  },
  offline: {
    backgroundColor: "rgba(242,184,91,0.12)",
    borderColor: fiticianTokens.colors.amber,
  },
  success: {
    backgroundColor: "rgba(102,200,159,0.12)",
    borderColor: fiticianTokens.colors.success,
  },
  warning: {
    backgroundColor: "rgba(242,184,91,0.12)",
    borderColor: fiticianTokens.colors.amber,
  },
};

export function Notice({
  actionLabel,
  message,
  onAction,
  title,
  variant = "info",
}: NoticeProps) {
  return (
    <View accessibilityRole="alert" style={[styles.notice, noticeStyles[variant]]}>
      {title ? <Text style={styles.noticeTitle}>{title}</Text> : null}
      <Text style={styles.noticeMessage}>{message}</Text>
      {actionLabel && onAction ? (
        <Button label={actionLabel} onPress={onAction} variant="secondary" />
      ) : null}
    </View>
  );
}

export interface EmptyStateProps {
  readonly actionLabel?: string;
  readonly children?: ReactNode;
  readonly onAction?: () => void;
  readonly title: string;
}

export function EmptyState({ actionLabel, children, onAction, title }: EmptyStateProps) {
  return (
    <View style={styles.emptyState}>
      <Text style={styles.noticeTitle}>{title}</Text>
      {typeof children === "string" ? <Text style={styles.noticeMessage}>{children}</Text> : children}
      {actionLabel && onAction ? (
        <Button label={actionLabel} onPress={onAction} variant="secondary" />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  emptyState: {
    alignItems: "center",
    gap: fiticianTokens.spacing[3],
    justifyContent: "center",
    padding: fiticianTokens.spacing[6],
  },
  notice: {
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[2],
    padding: fiticianTokens.spacing[4],
  },
  noticeMessage: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
  },
  noticeTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 24,
  },
  skeleton: {
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    opacity: 0.78,
  },
});
