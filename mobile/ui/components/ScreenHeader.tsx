import { type ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";

import { RTL_LAYOUT, RTL_ROW, RTL_TEXT } from "../rtl";
import { fiticianTokens } from "../tokens";

export interface ScreenHeaderProps {
  readonly action?: ReactNode;
  readonly brand?: string;
  readonly compact?: boolean;
  readonly eyebrow?: string;
  readonly subtitle?: string;
  readonly title: string;
}

export function ScreenHeader({
  action,
  brand = "FITICIAN",
  compact = false,
  eyebrow,
  subtitle,
  title,
}: ScreenHeaderProps) {
  return (
    <View style={[styles.header, RTL_LAYOUT, compact && styles.compact]}>
      <View style={[styles.topRow, RTL_ROW]}>
        <Text style={styles.brand}>{brand}</Text>
        {action}
      </View>
      <View style={styles.copy}>
        {eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}
        <Text accessibilityRole="header" style={[styles.title, compact && styles.compactTitle]}>{title}</Text>
        {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  brand: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    letterSpacing: 1.8,
    writingDirection: "ltr",
  },
  compact: {
    gap: fiticianTokens.spacing[2],
  },
  compactTitle: {
    fontSize: fiticianTokens.typography.fontSize.h2,
    lineHeight: 32,
  },
  copy: {
    alignItems: "stretch",
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
  },
  eyebrow: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
  },
  header: {
    gap: fiticianTokens.spacing[3],
    width: "100%",
  },
  subtitle: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
  },
  title: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 40,
  },
  topRow: {
    alignItems: "center",
    justifyContent: "space-between",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
  },
});
