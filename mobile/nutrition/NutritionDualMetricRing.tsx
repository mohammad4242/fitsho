import * as ExpoRouter from "expo-router";
import { useCallback, useRef } from "react";
import { Animated, Easing, StyleSheet, Text, View } from "react-native";
import Svg, { Circle } from "react-native-svg";

import { fiticianTokens } from "../ui/tokens";

const AnimatedCircle = Animated.createAnimatedComponent(Circle);

type NutritionDualMetricRingProps = {
  readonly activityColor?: string;
  readonly animationDuration?: number;
  readonly animateOnFocus?: boolean;
  readonly bmrColor?: string;
  readonly label: string;
  readonly primaryValue: number;
  readonly secondaryValue: number;
  readonly size?: number;
  readonly strokeWidth?: number;
  readonly total: number;
};

type NutritionDualMetricRingContentProps = {
  readonly activityColor: string;
  readonly animateProgress: number | Animated.Value;
  readonly bmrColor: string;
  readonly combinedProgress: number;
  readonly label: string;
  readonly primaryProgress: number;
  readonly secondaryProgress: number;
  readonly size: number;
  readonly strokeWidth: number;
};

export function NutritionDualMetricRing({
  activityColor = fiticianTokens.colors.aqua,
  animationDuration = 900,
  animateOnFocus = true,
  bmrColor = fiticianTokens.colors.blue,
  label,
  primaryValue,
  secondaryValue,
  size = 94,
  strokeWidth = 7,
  total,
}: NutritionDualMetricRingProps) {
  const safeTotal = total > 0 ? total : 1;
  const primaryProgress = clamp(primaryValue / safeTotal);
  const secondaryProgress = clamp(secondaryValue / safeTotal);
  const combinedProgress = clamp((primaryValue + secondaryValue) / safeTotal);

  const contentProps: NutritionDualMetricRingContentProps = {
    activityColor,
    animateProgress: 1,
    bmrColor,
    combinedProgress,
    label,
    primaryProgress,
    secondaryProgress,
    size,
    strokeWidth,
  };
  if (!animateOnFocus) return <NutritionDualMetricRingContent {...contentProps} />;
  return <FocusedNutritionDualMetricRing {...contentProps} animationDuration={animationDuration} />;
}

function FocusedNutritionDualMetricRing({
  animationDuration,
  ...props
}: Omit<NutritionDualMetricRingContentProps, "animateProgress"> & {
  readonly animationDuration: number;
}) {
  const animatedProgress = useRef(new Animated.Value(0)).current;
  const animate = useCallback(() => {
    animatedProgress.stopAnimation();
    animatedProgress.setValue(0);
    Animated.timing(animatedProgress, {
      duration: animationDuration,
      easing: Easing.out(Easing.cubic),
      toValue: 1,
      useNativeDriver: false,
    }).start();
  }, [animatedProgress, animationDuration]);

  const useFocusEffect = typeof ExpoRouter.useFocusEffect === "function"
    ? ExpoRouter.useFocusEffect
    : (_effect: ExpoRouter.EffectCallback) => undefined;
  useFocusEffect(useCallback(() => {
    animate();
    return () => animatedProgress.stopAnimation();
  }, [animate, animatedProgress]));

  return <NutritionDualMetricRingContent {...props} animateProgress={animatedProgress} />;
}

function NutritionDualMetricRingContent({
  activityColor,
  animateProgress,
  bmrColor,
  combinedProgress,
  label,
  primaryProgress,
  secondaryProgress,
  size,
  strokeWidth,
}: NutritionDualMetricRingContentProps) {
  const radius = (size - strokeWidth * 2 - 4) / 2;
  const circumference = 2 * Math.PI * radius;
  const primaryOffset = getOffset(animateProgress, primaryProgress, circumference);
  const secondaryOffset = getOffset(animateProgress, secondaryProgress, circumference);
  const percent = Math.round(combinedProgress * 100);
  const center = size / 2;

  return (
    <View
      accessible
      accessibilityLabel={label}
      accessibilityRole="progressbar"
      accessibilityValue={{ max: 100, min: 0, now: percent }}
      style={[styles.frame, { height: size, width: size }]}
    >
      <Svg height={size} style={styles.svg} width={size}>
        <Circle
          cx={center}
          cy={center}
          fill="transparent"
          r={radius}
          stroke={fiticianTokens.colors.progressTrack}
          strokeWidth={strokeWidth}
        />
        <Circle
          cx={center}
          cy={center}
          fill="transparent"
          r={radius - strokeWidth - 2}
          stroke={fiticianTokens.colors.progressTrack}
          strokeWidth={strokeWidth}
        />
        <AnimatedCircle
          cx={center}
          cy={center}
          fill="transparent"
          origin={`${center}, ${center}`}
          r={radius}
          rotation="-90"
          stroke={bmrColor}
          strokeDasharray={`${circumference} ${circumference}`}
          strokeDashoffset={primaryOffset}
          strokeLinecap="round"
          strokeWidth={strokeWidth}
        />
        <AnimatedCircle
          cx={center}
          cy={center}
          fill="transparent"
          origin={`${center}, ${center}`}
          r={radius - strokeWidth - 2}
          rotation="-90"
          stroke={activityColor}
          strokeDasharray={`${circumference} ${circumference}`}
          strokeDashoffset={secondaryOffset}
          strokeLinecap="round"
          strokeWidth={strokeWidth}
        />
      </Svg>
      <View pointerEvents="none" style={styles.copy}>
        <Text style={styles.value}>{percent.toLocaleString("fa-IR")}٪</Text>
        <Text numberOfLines={1} style={styles.label}>TDEE</Text>
      </View>
    </View>
  );
}

function getOffset(progress: number | Animated.Value, share: number, circumference: number) {
  if (typeof progress === "number") return circumference * (1 - share * progress);
  return progress.interpolate({
    inputRange: [0, 1],
    outputRange: [circumference, circumference * (1 - share)],
  });
}

function clamp(value: number): number {
  return Number.isFinite(value) ? Math.min(1, Math.max(0, value)) : 0;
}

const styles = StyleSheet.create({
  copy: {
    alignItems: "center",
    bottom: 0,
    justifyContent: "center",
    left: 0,
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
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: 9,
  },
  svg: {
    transform: [{ rotateZ: "0deg" }],
  },
  value: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.lg,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
  },
});
