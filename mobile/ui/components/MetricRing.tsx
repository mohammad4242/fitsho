import * as ExpoRouter from "expo-router";
import { useCallback, useEffect, useRef } from "react";
import { Animated, Easing, StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";
import Svg, { Circle } from "react-native-svg";

import { fiticianTokens } from "../tokens";
import { calculateRingGeometry, clampProgress } from "../visualMetrics";

const AnimatedCircle = Animated.createAnimatedComponent(Circle);

export interface MetricRingProps {
  readonly color?: string;
  readonly animateOnFocus?: boolean;
  readonly animationDuration?: number;
  readonly label: string;
  readonly progress: number;
  readonly showLabel?: boolean;
  readonly size?: number;
  readonly strokeWidth?: number;
  readonly style?: StyleProp<ViewStyle>;
  readonly valueLabel?: string;
}

export function MetricRing({
  animateOnFocus = false,
  animationDuration = 900,
  color = fiticianTokens.colors.aqua,
  label,
  progress,
  showLabel = true,
  size = 92,
  strokeWidth = 8,
  style,
  valueLabel,
}: MetricRingProps) {
  const contentProps = {
    color,
    label,
    progress,
    showLabel,
    size,
    strokeWidth,
    style,
    valueLabel,
  };

  if (animateOnFocus) {
    return <FocusedMetricRing {...contentProps} animationDuration={animationDuration} />;
  }

  return <MetricRingContent {...contentProps} />;
}

type MetricRingContentProps = {
  readonly color: string;
  readonly label: string;
  readonly progress: number;
  readonly progressDashOffset?: number | Animated.AnimatedInterpolation<number>;
  readonly showLabel: boolean;
  readonly size: number;
  readonly strokeWidth: number;
  readonly style?: StyleProp<ViewStyle>;
  readonly valueLabel?: string;
};

const useAvailableFocusEffect = typeof ExpoRouter.useFocusEffect === "function"
  ? ExpoRouter.useFocusEffect
  : (_effect: ExpoRouter.EffectCallback) => undefined;

function FocusedMetricRing({
  animationDuration,
  ...props
}: Omit<MetricRingContentProps, "progressDashOffset"> & { readonly animationDuration: number }) {
  const clamped = clampProgress(props.progress);
  const geometry = calculateRingGeometry(props.size, props.strokeWidth, clamped);
  const animatedProgress = useRef(new Animated.Value(0)).current;
  const progressRef = useRef(clamped);
  const focusedRef = useRef(false);
  const lastAnimatedProgress = useRef<number | null>(null);
  const animationRef = useRef<Animated.CompositeAnimation | null>(null);
  progressRef.current = clamped;

  const animateTo = useCallback((target: number, reset: boolean) => {
    animationRef.current?.stop?.();
    if (reset) animatedProgress.setValue(0);
    const animation = Animated.timing(animatedProgress, {
      duration: animationDuration,
      easing: Easing.out(Easing.cubic),
      toValue: target,
      useNativeDriver: false,
    });
    animationRef.current = animation;
    animation.start(({ finished }) => {
      if (finished && animationRef.current === animation) animationRef.current = null;
    });
  }, [animatedProgress, animationDuration]);

  useAvailableFocusEffect(useCallback(() => {
    focusedRef.current = true;
    lastAnimatedProgress.current = progressRef.current;
    animateTo(progressRef.current, true);

    return () => {
      focusedRef.current = false;
      lastAnimatedProgress.current = null;
      animationRef.current?.stop?.();
      animationRef.current = null;
    };
  }, [animateTo]));

  useEffect(() => {
    if (!focusedRef.current || lastAnimatedProgress.current === clamped) return;
    lastAnimatedProgress.current = clamped;
    animateTo(clamped, false);
  }, [animateTo, clamped]);

  const animatedDashOffset = animatedProgress.interpolate({
    inputRange: [0, 1],
    outputRange: [geometry.circumference, geometry.dashOffset],
  });

  return <MetricRingContent {...props} progressDashOffset={animatedDashOffset} />;
}

function MetricRingContent({
  color,
  label,
  progress,
  progressDashOffset,
  showLabel,
  size,
  strokeWidth,
  style,
  valueLabel,
}: MetricRingContentProps) {
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
        {progressDashOffset === undefined ? (
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
        ) : (
          <AnimatedCircle
            cx={center}
            cy={center}
            fill="transparent"
            origin={`${center}, ${center}`}
            r={geometry.radius}
            rotation="-90"
            stroke={color}
            strokeDasharray={`${geometry.circumference} ${geometry.circumference}`}
            strokeDashoffset={progressDashOffset}
            strokeLinecap="round"
            strokeWidth={strokeWidth}
          />
        )}
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
