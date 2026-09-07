import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { Button } from "../../ui/components";
import { Screen } from "../../ui/layout";
import { fiticianTokens } from "../../ui/tokens";

export default function PublicEntryScreen() {
  const router = useRouter();
  return (
    <Screen contentWidth="reading" contentContainerStyle={styles.screen}>
      <View style={styles.content}>
        <Text style={styles.brand}>FITICIAN</Text>
        <Text accessibilityRole="header" style={styles.title}>برنامه‌ای که با تو جلو می‌آید.</Text>
        <Text style={styles.description}>همراه هوشمند تمرین و تغذیه، متناسب با مسیر واقعی تو.</Text>
        <Button label="ورود" onPress={() => router.push("/auth/sign-in")} />
        <Pressable accessibilityRole="button" onPress={() => router.push("/auth/register")}>
          <Text style={styles.link}>ساخت حساب جدید</Text>
        </Pressable>
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
    gap: fiticianTokens.spacing[4],
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
  link: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    padding: fiticianTokens.spacing[3],
    textAlign: "center",
    writingDirection: "rtl",
  },
  screen: {
    justifyContent: "center",
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 42,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
