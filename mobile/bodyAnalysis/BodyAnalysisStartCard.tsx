import { Image, StyleSheet, Text, View, type ImageSourcePropType } from "react-native";

import { fiticianTokens } from "../ui/tokens";
import { BodyAnalysisCameraButton } from "./BodyAnalysisCameraButton";

const bodyAnalysisImage = require("../assets/body-analysis/bodyanalysis.jpg") as ImageSourcePropType;

export function BodyAnalysisStartCard({
  sessionCount,
  onStart,
}: {
  readonly sessionCount: number;
  readonly onStart: () => void;
}) {
  return (
    <View style={styles.card}>
      <View style={styles.heading}>
        <View style={styles.copy}>
          <Text style={styles.title}>جلسه جدید آنالیز بدن</Text>
          <View style={styles.countPill}>
            <Text style={styles.countText}>{formatCount(sessionCount)} جلسه تحلیل ثبت‌شده</Text>
            <View style={styles.countDot} />
          </View>
        </View>
        <View style={styles.media}>
          <Image accessibilityIgnoresInvertColors source={bodyAnalysisImage} style={styles.image} />
          <View style={styles.scanLine} />
        </View>
      </View>
      <BodyAnalysisCameraButton label="شروع جلسه عکس" onPress={onStart} />
    </View>
  );
}

function formatCount(value: number): string {
  return new Intl.NumberFormat("fa-IR").format(value);
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[3],
    shadowColor: "#000000",
    shadowOpacity: 0.22,
    shadowRadius: 10,
  },
  copy: {
    alignItems: "stretch",
    flex: 1,
    gap: fiticianTokens.spacing[2],
  },
  countDot: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    height: 7,
    shadowColor: fiticianTokens.colors.aqua,
    shadowOpacity: 0.8,
    shadowRadius: 7,
    width: 7,
  },
  countPill: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.aquaAtmosphere,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    alignSelf: "flex-start",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  countText: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  heading: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
  image: {
    height: "100%",
    width: "100%",
  },
  media: {
    backgroundColor: fiticianTokens.colors.canvas,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    height: 70,
    overflow: "hidden",
    position: "relative",
    width: 62,
  },
  scanLine: {
    backgroundColor: fiticianTokens.colors.aqua,
    height: 1,
    left: 0,
    opacity: 0.9,
    position: "absolute",
    right: 0,
    shadowColor: fiticianTokens.colors.aqua,
    shadowOpacity: 0.8,
    shadowRadius: 5,
    top: "38%",
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.lg,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 25,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
