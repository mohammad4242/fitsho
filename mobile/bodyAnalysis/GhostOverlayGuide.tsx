import { Image, StyleSheet, Text, View, type DimensionValue } from "react-native";

import type { Sex } from "@fitician/core/profile";
import type { BodyPhotoSide, BodyPhotoView } from "@fitician/core/body-photos";

import { fiticianTokens } from "../ui/tokens";
import {
  getGhostOverlayLayout,
  resolveGhostOverlayVariant,
} from "./ghostOverlay";
import { ghostOverlayAssets } from "./ghostOverlayAssets";

export interface GhostOverlayGuideProps {
  readonly sideProfile?: BodyPhotoSide;
  readonly sex?: Sex | null;
  readonly view: BodyPhotoView;
  readonly ghostScale?: number;
}

export function GhostOverlayGuide({
  sideProfile = "right",
  sex,
  view,
  ghostScale = 1,
}: GhostOverlayGuideProps) {
  const variant = resolveGhostOverlayVariant(sex);
  const layout = getGhostOverlayLayout(view, ghostScale, sideProfile, variant);
  const lineLeft = `${layout.privacyLine.start.x * 100}%` as DimensionValue;
  const lineWidth = `${(layout.privacyLine.end.x - layout.privacyLine.start.x) * 100}%` as DimensionValue;

  return (
    <View
      accessibilityLabel="راهنمای جای‌گیری بدن"
      pointerEvents="none"
      style={styles.overlay}
    >
      <View
        accessibilityLabel="خط حفظ حریم خصوصی"
        style={[
          styles.privacyLine,
          {
            left: lineLeft,
            top: `${layout.privacyLine.anchor.y * 100}%` as DimensionValue,
            width: lineWidth,
          },
        ]}
      >
        <Text style={styles.privacyLabel}>خط حفظ حریم خصوصی</Text>
      </View>
      <View
        accessibilityLabel={`شبح ${view === "front" ? "روبه‌رو" : view === "side" ? "نیمرخ" : "پشت"}`}
        style={[
          styles.assetFrame,
          {
            transform: [
              ...(layout.mirrored ? [{ scaleX: -1 }] : []),
              { scale: layout.scale },
            ],
          },
        ]}
      >
        <Image
          accessibilityLabel=""
          resizeMode="contain"
          source={ghostOverlayAssets[variant][view]}
          style={[
            styles.asset,
            {
              top: `${layout.assetCalibration.translateYRatio * 100}%` as DimensionValue,
              transform: [{ scale: layout.assetCalibration.scale }],
            },
          ]}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  asset: {
    height: "100%",
    opacity: 0.48,
    position: "relative",
    transformOrigin: "center",
    width: "100%",
  },
  assetFrame: {
    alignItems: "center",
    bottom: 0,
    left: 0,
    justifyContent: "center",
    position: "absolute",
    right: 0,
    top: 0,
    transformOrigin: "center",
  },
  overlay: {
    bottom: 0,
    left: 0,
    overflow: "hidden",
    position: "absolute",
    right: 0,
    top: 0,
  },
  privacyLabel: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    marginTop: fiticianTokens.spacing[1],
    textAlign: "center",
    writingDirection: "rtl",
  },
  privacyLine: {
    alignItems: "center",
    borderTopColor: fiticianTokens.colors.aqua,
    borderTopWidth: 2,
    height: 28,
    position: "absolute",
    zIndex: 2,
  },
});
