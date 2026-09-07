import { StyleSheet, Text, View } from "react-native";
import { type ReactNode } from "react";

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
        <Text style={styles.brand}>FITICIAN</Text>
        <Text accessibilityRole="header" style={styles.title}>{title}</Text>
        <Text style={styles.description}>{description}</Text>
        {children}
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
