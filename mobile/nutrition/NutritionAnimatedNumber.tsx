import { useEffect, useRef, useState } from "react";
import { Animated, Easing, Text, type StyleProp, type TextStyle } from "react-native";

export function NutritionAnimatedNumber({
  duration = 900,
  prefix = "",
  style,
  value,
}: {
  readonly duration?: number;
  readonly prefix?: string;
  readonly style?: StyleProp<TextStyle>;
  readonly value: number;
}) {
  const progress = useRef(new Animated.Value(0)).current;
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    const listenerId = progress.addListener(({ value: nextProgress }) => {
      setDisplayValue(value * nextProgress);
    });
    progress.setValue(0);
    const animation = Animated.timing(progress, {
      duration,
      easing: Easing.out(Easing.cubic),
      toValue: 1,
      useNativeDriver: false,
    });
    animation.start();

    return () => {
      animation.stop();
      progress.removeListener(listenerId);
    };
  }, [duration, progress, value]);

  return <Text style={style}>{prefix}{formatNumber(displayValue)}</Text>;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1 }).format(value);
}
