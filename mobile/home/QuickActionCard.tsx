import { Pressable, StyleSheet, Text, View, type ImageSourcePropType } from "react-native";

import { AppIcon, Media } from "../ui/components";
import { fiticianTokens } from "../ui/tokens";

export interface QuickActionCardProps {
  readonly icon: "bodyAnalysis" | "foodLog";
  readonly image: ImageSourcePropType;
  readonly onPress: () => void;
  readonly subtitle: string;
  readonly title: string;
}

export function QuickActionCard({ icon, image, onPress, subtitle, title }: QuickActionCardProps) {
  return (
    <Pressable
      accessibilityLabel={title}
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
    >
      <Media accessibilityLabel="" source={image} style={styles.image} />
      <View pointerEvents="none" style={styles.scrim} />
      <View pointerEvents="none" style={[styles.corner, styles.cornerStart]} />
      <View pointerEvents="none" style={[styles.corner, styles.cornerEnd]} />
      <View pointerEvents="none" style={styles.scanLine} />
      <View pointerEvents="none" style={styles.content}>
        <View style={styles.iconBadge}>
          <AppIcon color={fiticianTokens.colors.aqua} name={icon} size={fiticianTokens.iconSize.md} />
        </View>
        <View style={styles.copy}>
          <Text style={styles.title}>{title}</Text>
          <Text style={styles.subtitle}>{subtitle}</Text>
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    height: 150,
    overflow: "hidden",
    position: "relative",
    shadowColor: fiticianTokens.shadows.soft.color,
    shadowOffset: fiticianTokens.shadows.soft.offset,
    shadowOpacity: fiticianTokens.shadows.soft.opacity,
    shadowRadius: fiticianTokens.shadows.soft.radius,
    elevation: fiticianTokens.shadows.soft.elevation,
    flex: 1,
  },
  content: {
    alignItems: "flex-start",
    bottom: fiticianTokens.spacing[3],
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[2],
    left: fiticianTokens.spacing[3],
    position: "absolute",
    right: fiticianTokens.spacing[3],
  },
  corner: {
    borderColor: fiticianTokens.colors.aqua,
    height: 18,
    opacity: 0.7,
    position: "absolute",
    top: fiticianTokens.spacing[3],
    width: 18,
  },
  cornerEnd: {
    borderRightWidth: 2,
    borderTopWidth: 2,
    right: fiticianTokens.spacing[3],
  },
  cornerStart: {
    borderLeftWidth: 2,
    borderTopWidth: 2,
    left: fiticianTokens.spacing[3],
  },
  copy: {
    flex: 1,
    gap: 2,
  },
  iconBadge: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.mediaOverlay,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    height: 44,
    justifyContent: "center",
    width: 44,
  },
  image: {
    borderRadius: 0,
    height: "100%",
    width: "100%",
  },
  pressed: {
    opacity: 0.86,
    transform: [{ scale: fiticianTokens.motion.pressedScale }],
  },
  scrim: {
    backgroundColor: fiticianTokens.colors.scrim,
    bottom: 0,
    left: 0,
    position: "absolute",
    right: 0,
    top: 0,
  },
  scanLine: {
    backgroundColor: fiticianTokens.colors.aqua,
    height: 1,
    left: fiticianTokens.spacing[3],
    opacity: 0.68,
    position: "absolute",
    right: fiticianTokens.spacing[3],
    shadowColor: fiticianTokens.colors.aqua,
    shadowOpacity: 0.7,
    shadowRadius: 7,
    top: "54%",
  },
  subtitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    lineHeight: 18,
    textAlign: "right",
    writingDirection: "rtl",
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.lg,
    lineHeight: 27,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
