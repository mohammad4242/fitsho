import { StyleSheet, Text, View } from "react-native";

import { fiticianTokens } from "../ui/tokens";

const featureCards = [
  {
    icon: "🔒",
    title: "حفظ ۱۰۰٪ حریم خصوصی",
    subtitle: "برش خودکار چهره روی گوشی پیش از بارگذاری",
  },
  {
    icon: "📐",
    title: "راهنمای استاندارد Ghost",
    subtitle: "عکاسی دقیق در ۳ زاویه روبه‌رو، نیمرخ و پشت",
  },
  {
    icon: "📊",
    title: "دورسنجی و تحلیل روند",
    subtitle: "پایش دور کمر، باسن، شانه و اسلایدر قبل/بعد",
  },
] as const;

export function BodyAnalysisLandingHero() {
  return (
    <View style={styles.container}>
      <View style={styles.badge}>
        <View style={styles.badgeDot} />
        <Text style={styles.badgeText}>آنالیز هوشمند ترکیب و فرم بدن</Text>
      </View>
      <Text accessibilityRole="header" style={styles.title}>
        <Text style={styles.titleWhite}>Body </Text>
        <Text style={styles.titleAqua}>Analysis</Text>
      </Text>
      <Text style={styles.subtitle}>
        پایش دقیق روند تغییرات فیزیکی، دورسنجی‌ها و ثبت بصری پیشرفت بدن
      </Text>
      <Text style={styles.intro}>
        اختیاری — برای برنامه تمرینی دقیق‌تر و شخصی‌تر، عکس‌های استاندارد بدن را اضافه کن.
      </Text>
      <View accessibilityLabel="امکانات آنالیز بدن" style={styles.features}>
        {featureCards.map((feature) => (
          <View key={feature.title} style={styles.featureCard}>
            <View accessibilityLabel={feature.icon} style={styles.featureIcon}>
              <Text style={styles.featureIconText}>{feature.icon}</Text>
            </View>
            <View style={styles.featureCopy}>
              <Text style={styles.featureTitle}>{feature.title}</Text>
              <Text style={styles.featureSubtitle}>{feature.subtitle}</Text>
            </View>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignItems: "center",
    alignSelf: "flex-start",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[2],
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  badgeDot: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    height: 7,
    shadowColor: fiticianTokens.colors.aqua,
    shadowOpacity: 0.75,
    shadowRadius: 7,
    width: 7,
  },
  badgeText: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  container: {
    alignItems: "flex-start",
    gap: fiticianTokens.spacing[3],
  },
  featureCard: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[3],
    width: "100%",
  },
  featureCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  featureIcon: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.aquaAtmosphere,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    height: 44,
    justifyContent: "center",
    width: 44,
  },
  featureIconText: {
    fontSize: 21,
    lineHeight: 25,
  },
  featureSubtitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 19,
    textAlign: "right",
    writingDirection: "rtl",
  },
  featureTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 22,
    textAlign: "right",
    writingDirection: "rtl",
  },
  features: {
    alignSelf: "stretch",
    gap: fiticianTokens.spacing[2],
    marginTop: fiticianTokens.spacing[1],
  },
  intro: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 24,
    textAlign: "right",
    writingDirection: "rtl",
  },
  subtitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 26,
    textAlign: "right",
    writingDirection: "rtl",
  },
  title: {
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: fiticianTokens.typography.fontSize.display,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    letterSpacing: -1.6,
    lineHeight: 44,
    textAlign: "left",
    writingDirection: "ltr",
  },
  titleAqua: {
    color: fiticianTokens.colors.aqua,
  },
  titleWhite: {
    color: "#ffffff",
  },
});
