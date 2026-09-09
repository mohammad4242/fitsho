import { Image, StyleSheet, Text, View, type ImageSourcePropType } from "react-native";

import { fiticianTokens } from "../ui/tokens";
import { BodyAnalysisCameraButton } from "./BodyAnalysisCameraButton";

const bodyAnalysisImage = require("../assets/body-analysis/bodyanalysis.jpg") as ImageSourcePropType;

export function BodyAnalysisEmptyState({ onStart }: { readonly onStart: () => void }) {
  return (
    <View style={styles.container}>
      <View style={styles.visual}>
        <Image accessibilityIgnoresInvertColors source={bodyAnalysisImage} style={styles.image} />
        <View style={styles.overlay} />
        <View style={[styles.corner, styles.cornerTopLeft]} />
        <View style={[styles.corner, styles.cornerTopRight]} />
        <View style={[styles.corner, styles.cornerBottomLeft]} />
        <View style={[styles.corner, styles.cornerBottomRight]} />
        <View style={styles.scanLine} />
        <View style={styles.hudBadge}>
          <View style={styles.hudDot} />
          <Text style={styles.hudText}>اسکن هوشمند دوربین و بیومتریک بدن</Text>
        </View>
      </View>
      <View style={styles.content}>
        <Text accessibilityRole="header" style={styles.title}>هیچ عکسی ثبت نشده است</Text>
        <Text style={styles.body}>برای شروع تحلیل، از بدن خود در حالت ایستاده عکس‌های استاندارد بگیر.</Text>
        <View style={styles.steps}>
          <EmptyStep number="۱" title="عکاسی ۳ زاویه" subtitle="روبه‌رو، نیمرخ، پشت" />
          <EmptyStep number="۲" title="برش امن چهره" subtitle="کاملاً محرمانه در گوشی" />
          <EmptyStep number="۳" title="تحلیل و دورسنجی" subtitle="نمودار و روند پیشرفت" />
        </View>
        <BodyAnalysisCameraButton label="ثبت عکس‌های جدید" onPress={onStart} />
      </View>
    </View>
  );
}

function EmptyStep({
  number,
  subtitle,
  title,
}: {
  readonly number: string;
  readonly subtitle: string;
  readonly title: string;
}) {
  return (
    <View style={styles.step}>
      <View style={styles.stepBadge}><Text style={styles.stepNumber}>{number}</Text></View>
      <View style={styles.stepCopy}>
        <Text style={styles.stepTitle}>{title}</Text>
        <Text style={styles.stepSubtitle}>{subtitle}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  body: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 24,
    textAlign: "right",
    writingDirection: "rtl",
  },
  container: {
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.extraLarge,
    borderWidth: 1,
    gap: fiticianTokens.spacing[4],
    overflow: "hidden",
    padding: fiticianTokens.spacing[3],
  },
  content: {
    gap: fiticianTokens.spacing[3],
  },
  corner: {
    borderColor: fiticianTokens.colors.aqua,
    height: 20,
    position: "absolute",
    width: 20,
  },
  cornerBottomLeft: {
    borderBottomWidth: 2,
    borderLeftWidth: 2,
    bottom: 12,
    left: 12,
  },
  cornerBottomRight: {
    borderBottomWidth: 2,
    borderRightWidth: 2,
    bottom: 12,
    right: 12,
  },
  cornerTopLeft: {
    borderLeftWidth: 2,
    borderTopWidth: 2,
    left: 12,
    top: 12,
  },
  cornerTopRight: {
    borderRightWidth: 2,
    borderTopWidth: 2,
    right: 12,
    top: 12,
  },
  hudBadge: {
    alignItems: "center",
    backgroundColor: "rgba(2,9,10,0.84)",
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    bottom: 12,
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[2],
    left: 12,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
    position: "absolute",
    right: 12,
  },
  hudDot: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    height: 7,
    shadowColor: fiticianTokens.colors.aqua,
    shadowOpacity: 0.8,
    shadowRadius: 7,
    width: 7,
  },
  hudText: {
    color: fiticianTokens.colors.ink,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  image: {
    height: "100%",
    width: "100%",
  },
  overlay: {
    backgroundColor: "rgba(2,9,10,0.22)",
    bottom: 0,
    left: 0,
    position: "absolute",
    right: 0,
    top: 0,
  },
  scanLine: {
    backgroundColor: fiticianTokens.colors.aqua,
    height: 2,
    left: "5%",
    opacity: 0.9,
    position: "absolute",
    right: "5%",
    shadowColor: fiticianTokens.colors.aqua,
    shadowOpacity: 0.85,
    shadowRadius: 10,
    top: "32%",
  },
  step: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[3],
  },
  stepBadge: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.aquaAtmosphere,
    borderColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    height: 30,
    justifyContent: "center",
    width: 30,
  },
  stepCopy: {
    flex: 1,
    gap: 2,
  },
  stepNumber: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
  },
  stepSubtitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 18,
    textAlign: "right",
    writingDirection: "rtl",
  },
  stepTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 22,
    textAlign: "right",
    writingDirection: "rtl",
  },
  steps: {
    gap: fiticianTokens.spacing[2],
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 29,
    textAlign: "right",
    writingDirection: "rtl",
  },
  visual: {
    alignSelf: "center",
    aspectRatio: 4 / 5,
    backgroundColor: fiticianTokens.colors.canvas,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    maxWidth: 320,
    overflow: "hidden",
    position: "relative",
    width: "100%",
  },
});
