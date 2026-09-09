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
    shadowColor: "#000000",
    shadowOffset: { height: 4, width: 0 },
    shadowOpacity: 0.24,
    shadowRadius: 10,
    elevation: 3,
  },
  content: {
    alignItems: "flex-start",
    bottom: 14,
    flexDirection: "row-reverse",
    gap: 10,
    left: 14,
    position: "absolute",
    right: 14,
  },
  copy: {
    flex: 1,
    gap: 2,
  },
  iconBadge: {
    alignItems: "center",
    backgroundColor: "rgba(2,6,7,0.72)",
    borderColor: "rgba(80,223,206,0.32)",
    borderRadius: 14,
    borderWidth: 1,
    height: 42,
    justifyContent: "center",
    width: 42,
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
    backgroundColor: "rgba(2,6,7,0.60)",
    bottom: 0,
    left: 0,
    position: "absolute",
    right: 0,
    top: 0,
  },
  subtitle: {
    color: "rgba(232,244,241,0.72)",
    fontFamily: "Vazirmatn",
    fontSize: 11,
    lineHeight: 18,
    textAlign: "right",
    writingDirection: "rtl",
  },
  title: {
    color: "#e8f4f1",
    fontFamily: "Lalezar",
    fontSize: 19,
    lineHeight: 27,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
