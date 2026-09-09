import { type ReactNode } from "react";
import {
  StyleSheet,
  Text,
  View,
  type StyleProp,
  type ViewProps,
  type ViewStyle,
} from "react-native";

import { fiticianTokens } from "../tokens";

export type PageHeadingDirection = "rtl" | "ltr";

export interface PageHeadingProps extends Pick<ViewProps, "testID"> {
  readonly action?: ReactNode;
  readonly compact?: boolean;
  readonly direction?: PageHeadingDirection;
  readonly eyebrow?: string;
  readonly style?: StyleProp<ViewStyle>;
  readonly supportingText?: string;
  readonly title: string;
}

export function PageHeading({
  action,
  compact = true,
  direction = "rtl",
  eyebrow,
  style,
  supportingText,
  testID,
  title,
}: PageHeadingProps) {
  const isRtl = direction === "rtl";
  const textStyle = { textAlign: isRtl ? "right" : "left", writingDirection: direction } as const;

  return (
    <View
      style={[
        styles.container,
        { direction, flexDirection: isRtl ? "row-reverse" : "row" },
        style,
      ]}
      testID={testID}
    >
      <View style={styles.copy}>
        {eyebrow ? <Text style={[styles.eyebrow, textStyle]}>{eyebrow}</Text> : null}
        <Text
          accessibilityRole="header"
          allowFontScaling
          style={[styles.title, compact && styles.compactTitle, textStyle]}
        >
          {title}
        </Text>
        {supportingText ? <Text style={[styles.supportingText, textStyle]}>{supportingText}</Text> : null}
      </View>
      {action ? <View style={styles.action}>{action}</View> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  action: {
    flexShrink: 0,
    minWidth: fiticianTokens.layout.minimumTouchTarget,
  },
  compactTitle: {
    fontSize: fiticianTokens.typography.fontSize.h2,
    lineHeight: 32,
  },
  container: {
    alignItems: "center",
    gap: fiticianTokens.spacing[3],
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    width: "100%",
  },
  copy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
  },
  eyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    letterSpacing: 0.7,
    lineHeight: 20,
  },
  supportingText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 40,
  },
});
