import { StyleSheet, Text, View } from "react-native";
import { type ReactNode } from "react";

import { AppIcon, Card } from "../components";
import { Screen } from "../layout";
import { fiticianTokens } from "../tokens";

export interface RouteEntryScreenProps {
  readonly children?: ReactNode;
  readonly description: string;
  readonly title: string;
}

export function RouteEntryScreen({ children, description, title }: RouteEntryScreenProps) {
  return (
    <Screen contentContainerStyle={styles.screen} contentWidth="reading" scroll={false}>
      <View style={styles.content}>
        <View style={styles.brandRow}>
          <Text style={styles.brand}>FITICIAN</Text>
          <View style={styles.brandMark}>
            <AppIcon color={fiticianTokens.colors.aqua} name="target" size={18} />
          </View>
        </View>
        <Card variant="hero" style={styles.hero}>
          <Text accessibilityRole="header" style={styles.title}>{title}</Text>
          <Text style={styles.description}>{description}</Text>
          {children}
        </Card>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  brand: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    letterSpacing: 1.4,
    textAlign: "left",
    writingDirection: "ltr",
  },
  brandMark: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    height: 36,
    justifyContent: "center",
    width: 36,
  },
  brandRow: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  content: {
    gap: fiticianTokens.spacing[3],
    maxWidth: fiticianTokens.layout.readingMaxWidth,
    width: "100%",
  },
  description: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "rtl",
  },
  hero: {
    gap: fiticianTokens.spacing[4],
    padding: fiticianTokens.spacing[5],
  },
  screen: {
    justifyContent: "center",
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 40,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
