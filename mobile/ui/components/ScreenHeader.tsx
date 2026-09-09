import { type ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";

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
    <View style={[styles.header, compact && styles.compact]}>
      <View style={styles.topRow}>
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
    alignItems: "flex-end",
    gap: fiticianTokens.spacing[1],
  },
  eyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  header: {
    gap: fiticianTokens.spacing[3],
    width: "100%",
  },
  subtitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
    textAlign: "right",
    writingDirection: "rtl",
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 40,
    textAlign: "right",
    writingDirection: "rtl",
  },
  topRow: {
    alignItems: "center",
    flexDirection: "row-reverse",
    justifyContent: "space-between",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
  },
});
