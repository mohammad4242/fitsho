import { StyleSheet, Text, View } from "react-native";

import { fiticianTokens } from "../tokens";

export interface RouteEntryScreenProps {
  readonly description: string;
  readonly title: string;
}

export function RouteEntryScreen({ description, title }: RouteEntryScreenProps) {
  return (
    <View style={styles.screen}>
      <View style={styles.content}>
        <Text style={styles.brand}>FITICIAN</Text>
        <Text accessibilityRole="header" style={styles.title}>{title}</Text>
        <Text style={styles.description}>{description}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  brand: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    letterSpacing: 1.4,
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
  },
  screen: {
    backgroundColor: fiticianTokens.colors.canvas,
    flex: 1,
    justifyContent: "center",
    paddingHorizontal: fiticianTokens.layout.screenPadding,
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 40,
  },
});
