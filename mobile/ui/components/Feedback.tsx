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
import { RTL_LAYOUT, RTL_TEXT } from "../rtl";
import { Button } from "./Button";

export interface SkeletonProps {
  readonly accessibilityLabel?: string;
  readonly height?: DimensionValue;
  readonly radius?: number;
  readonly style?: StyleProp<ViewStyle>;
  readonly width?: DimensionValue;
}

export function Skeleton({
  accessibilityLabel = "در حال بارگذاری",
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
  readonly compact?: boolean;
  readonly message: string;
  readonly onAction?: () => void;
  readonly title?: string;
  readonly variant?: NoticeVariant;
}

const noticeStyles: Record<NoticeVariant, ViewStyle> = {
  danger: {
    backgroundColor: fiticianTokens.colors.dangerSurface,
    borderColor: fiticianTokens.colors.danger,
  },
  info: {
    backgroundColor: fiticianTokens.colors.infoSurface,
    borderColor: fiticianTokens.colors.aqua,
  },
  offline: {
    backgroundColor: fiticianTokens.colors.warningSurface,
    borderColor: fiticianTokens.colors.amber,
  },
  success: {
    backgroundColor: fiticianTokens.colors.successSurface,
    borderColor: fiticianTokens.colors.success,
  },
  warning: {
    backgroundColor: fiticianTokens.colors.warningSurface,
    borderColor: fiticianTokens.colors.amber,
  },
};

export function Notice({
  actionLabel,
  compact = false,
  message,
  onAction,
  title,
  variant = "info",
}: NoticeProps) {
  return (
    <View
      accessibilityLiveRegion={variant === "danger" ? "assertive" : "polite"}
      accessibilityRole="alert"
      style={[styles.notice, RTL_LAYOUT, noticeStyles[variant], compact && styles.compactNotice]}
    >
      {title ? <Text style={[styles.noticeTitle, compact && styles.compactTitle]}>{title}</Text> : null}
      <Text style={[styles.noticeMessage, compact && styles.compactMessage]}>{message}</Text>
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
    <View style={[styles.emptyState, RTL_LAYOUT]}>
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
  compactMessage: {
    fontSize: fiticianTokens.typography.fontSize.compact,
    lineHeight: 20,
  },
  compactNotice: {
    gap: fiticianTokens.spacing[1],
    padding: fiticianTokens.spacing[3],
  },
  compactTitle: {
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 21,
  },
  notice: {
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[2],
    padding: fiticianTokens.spacing[4],
  },
  noticeMessage: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
  },
  noticeTitle: {
    ...RTL_TEXT,
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
