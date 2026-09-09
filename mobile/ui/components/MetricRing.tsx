import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";
import Svg, { Circle } from "react-native-svg";

import { fiticianTokens } from "../tokens";
import { calculateRingGeometry, clampProgress } from "../visualMetrics";

export interface MetricRingProps {
  readonly color?: string;
  readonly label: string;
  readonly progress: number;
  readonly showLabel?: boolean;
  readonly size?: number;
  readonly strokeWidth?: number;
  readonly style?: StyleProp<ViewStyle>;
  readonly valueLabel?: string;
}

export function MetricRing({
  color = fiticianTokens.colors.aqua,
  label,
  progress,
  showLabel = true,
  size = 92,
  strokeWidth = 8,
  style,
  valueLabel,
}: MetricRingProps) {
  const clamped = clampProgress(progress);
  const percent = Math.round(clamped * 100);
  const geometry = calculateRingGeometry(size, strokeWidth, clamped);
  const center = size / 2;

  return (
    <View
      accessible
      accessibilityLabel={label}
      accessibilityRole="progressbar"
      accessibilityValue={{ max: 100, min: 0, now: percent }}
      style={[styles.frame, { height: size, width: size }, style]}
    >
      <Svg height={size} style={styles.svg} width={size}>
        <Circle
          cx={center}
          cy={center}
          fill="transparent"
          r={geometry.radius}
          stroke={fiticianTokens.colors.progressTrack}
          strokeWidth={strokeWidth}
        />
        <Circle
          cx={center}
          cy={center}
          fill="transparent"
          origin={`${center}, ${center}`}
          r={geometry.radius}
          rotation="-90"
          stroke={color}
          strokeDasharray={`${geometry.circumference} ${geometry.circumference}`}
          strokeDashoffset={geometry.dashOffset}
          strokeLinecap="round"
          strokeWidth={strokeWidth}
        />
      </Svg>
      <View pointerEvents="none" style={styles.copy}>
        <Text style={styles.value}>{valueLabel ?? `${percent.toLocaleString("fa-IR")}٪`}</Text>
        {showLabel ? <Text numberOfLines={1} style={styles.label}>{label}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  copy: {
    alignItems: "center",
    bottom: 0,
    justifyContent: "center",
    left: 0,
    padding: fiticianTokens.spacing[2],
    position: "absolute",
    right: 0,
    top: 0,
  },
  frame: {
    alignItems: "center",
    justifyContent: "center",
  },
  label: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    marginTop: 1,
    maxWidth: "74%",
    textAlign: "center",
    writingDirection: "rtl",
  },
  svg: {
    transform: [{ rotateZ: "0deg" }],
  },
  value: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.lg,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "center",
  },
});
