import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { AppIcon, Button, CinematicSurface, Media } from "../../ui/components";
import { Screen } from "../../ui/layout";
import { fiticianTokens } from "../../ui/tokens";

export default function PublicEntryScreen() {
  const router = useRouter();
  return (
    <Screen contentWidth="reading" contentContainerStyle={styles.screen}>
      <View style={styles.content}>
        <View style={styles.brandRow}>
          <Text style={styles.brand}>FITICIAN</Text>
          <Text style={styles.eyebrow}>PERSONAL PERFORMANCE</Text>
        </View>
        <CinematicSurface accent style={styles.hero} variant="hero">
          <Media
            accessibilityLabel="تمرین قدرتی فیتیشن"
            source={require("../../assets/public-entry-hero.jpg")}
            style={styles.heroMedia}
          />
          <View pointerEvents="none" style={styles.heroScrim} />
          <View style={styles.heroContent}>
            <View style={styles.heroIcon}>
              <AppIcon accessibilityLabel="مسیر شخصی فیتشو" color={fiticianTokens.colors.aqua} name="target" size={fiticianTokens.iconSize.lg} />
            </View>
            <Text accessibilityRole="header" style={styles.title}>برنامه‌ای که با تو جلو می‌آید.</Text>
            <Text style={styles.description}>مسیر هوشمند تمرین و تغذیه، متناسب با بدن، هدف و زندگی واقعی تو.</Text>
            <View style={styles.pillRow}>
              <Text style={styles.pill}>تمرین</Text>
              <Text style={styles.pill}>تغذیه</Text>
              <Text style={styles.pill}>تحلیل بدن</Text>
            </View>
            <Button label="شروع شخصی‌سازی" onPress={() => router.push("/public-onboarding")} />
          </View>
        </CinematicSurface>
        <View style={styles.actions}>
          <Button label="ورود به حساب" onPress={() => router.push("/auth/sign-in")} variant="secondary" />
        </View>
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
  brandRow: {
    alignItems: "center",
    flexDirection: "row-reverse",
    justifyContent: "space-between",
  },
  content: {
    gap: fiticianTokens.spacing[4],
    width: "100%",
  },
  actions: {
    gap: fiticianTokens.spacing[3],
  },
  eyebrow: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    letterSpacing: 1.1,
    writingDirection: "ltr",
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
    minHeight: 500,
  },
  heroContent: {
    gap: fiticianTokens.spacing[4],
    justifyContent: "flex-end",
    minHeight: 500,
    padding: fiticianTokens.spacing[5],
  },
  heroMedia: {
    borderRadius: 0,
    bottom: 0,
    height: "100%",
    left: 0,
    position: "absolute",
    right: 0,
    top: 0,
    width: "100%",
  },
  heroIcon: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    height: 52,
    justifyContent: "center",
    width: 52,
  },
  heroScrim: {
    backgroundColor: "rgba(2,6,7,0.64)",
    bottom: 0,
    left: 0,
    position: "absolute",
    right: 0,
    top: 0,
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
  pill: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
    writingDirection: "rtl",
  },
  pillRow: {
    flexDirection: "row-reverse",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  screen: {
    paddingBottom: fiticianTokens.spacing[5],
    paddingTop: fiticianTokens.spacing[3],
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
