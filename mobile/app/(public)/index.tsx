import { Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { AppIcon, Button, CinematicSurface, Media } from "../../ui/components";
import { Screen } from "../../ui/layout";
import { fiticianTokens } from "../../ui/tokens";

const processStages = [
  { body: "تو را می‌شناسیم", number: "۰۱", title: "شناخت" },
  { body: "برنامه‌ات را می‌سازیم", number: "۰۲", title: "برنامه" },
  { body: "با راهنمایی اجرا می‌کنی", number: "۰۳", title: "تمرین" },
  { body: "همراه پیشرفتت تنظیم می‌کنیم", number: "۰۴", title: "تطبیق" },
] as const;

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
            <Text style={styles.heroEyebrow}>بدن تو، نقطه شروع برنامه</Text>
            <Text accessibilityRole="header" style={styles.title}>هر بدن، برنامه خودش را می‌خواهد.</Text>
            <Text style={styles.description}>تمرین و تغذیه‌ای متناسب با بدن، هدف و مسیر تو.</Text>
            <View style={styles.pillRow}>
              <Text style={styles.pill}>تمرین</Text>
              <Text style={styles.pill}>تغذیه</Text>
              <Text style={styles.pill}>تحلیل بدن</Text>
            </View>
            <Button label="برنامه من را بساز" onPress={() => router.push("/public-onboarding")} />
          </View>
        </CinematicSurface>
        <View style={styles.actions}>
          <Button label="ورود به حساب" onPress={() => router.push("/auth/sign-in")} variant="secondary" />
        </View>
        <Pressable accessibilityRole="button" onPress={() => router.push("/auth/register")}>
          <Text style={styles.link}>ساخت حساب جدید</Text>
        </Pressable>
        <CinematicSurface testID="public-entry-process" style={styles.process} variant="quiet">
          <View style={styles.processHeader}>
            <Text style={styles.processEyebrow}>فرایند فیتشو</Text>
            <Text accessibilityRole="header" style={styles.processTitle}>فیتشو چگونه برنامه تو را می‌سازد</Text>
          </View>
          <View style={styles.processList}>
            {processStages.map((stage, index) => (
              <View key={stage.number} style={[styles.processStage, index === processStages.length - 1 && styles.processStageLast]}>
                <View style={styles.stageMarker}>
                  <Text style={styles.stageNumber}>{stage.number}</Text>
                </View>
                <View style={styles.stageCopy}>
                  <Text style={styles.stageTitle}>{stage.title}</Text>
                  <Text style={styles.stageBody}>{stage.body}</Text>
                </View>
              </View>
            ))}
          </View>
        </CinematicSurface>
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
  heroEyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 22,
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
  process: {
    padding: fiticianTokens.spacing[4],
  },
  processEyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    letterSpacing: 0.4,
    textAlign: "right",
    writingDirection: "rtl",
  },
  processHeader: {
    gap: fiticianTokens.spacing[2],
  },
  processList: {
    marginTop: fiticianTokens.spacing[3],
  },
  processStage: {
    alignItems: "center",
    borderBottomColor: fiticianTokens.colors.line,
    borderBottomWidth: 1,
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingVertical: fiticianTokens.spacing[2],
  },
  processStageLast: {
    borderBottomWidth: 0,
    paddingBottom: 0,
  },
  processTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "rtl",
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
  stageBody: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "right",
    writingDirection: "rtl",
  },
  stageCopy: {
    flex: 1,
    gap: 2,
  },
  stageMarker: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    height: 32,
    justifyContent: "center",
    width: 32,
  },
  stageNumber: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    writingDirection: "ltr",
  },
  stageTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 22,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
