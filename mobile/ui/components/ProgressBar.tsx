import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";

import { RTL_LAYOUT } from "../rtl";
import { fiticianTokens } from "../tokens";

export interface ProgressBarProps {
  readonly color?: string;
  readonly label?: string;
  readonly progress: number;
  readonly style?: StyleProp<ViewStyle>;
}

export function ProgressBar({ color = fiticianTokens.colors.aqua, label, progress, style }: ProgressBarProps) {
  const clampedProgress = Math.min(1, Math.max(0, progress));
  return (
    <View
      accessible
      accessibilityLabel={label}
      accessibilityRole="progressbar"
      accessibilityValue={{ max: 100, min: 0, now: Math.round(clampedProgress * 100) }}
      style={[styles.track, RTL_LAYOUT, style]}
    >
      <View style={[styles.fill, { backgroundColor: color, width: `${clampedProgress * 100}%` }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  fill: {
    borderRadius: fiticianTokens.radii.pill,
    height: "100%",
    minWidth: 2,
  },
  track: {
    backgroundColor: "rgba(232,244,241,0.10)",
    borderRadius: fiticianTokens.radii.pill,
    height: 8,
    overflow: "hidden",
    width: "100%",
  },
});
