import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";

import { fiticianTokens } from "../tokens";

export interface MetricStripItem {
  readonly accent?: string;
  readonly label: string;
  readonly value: string;
}

export interface MetricStripProps {
  readonly items: readonly MetricStripItem[];
  readonly style?: StyleProp<ViewStyle>;
}

export function MetricStrip({ items, style }: MetricStripProps) {
  return (
    <View style={[styles.strip, style]}>
      {items.map((item, index) => (
        <View key={`${item.label}-${index}`} style={[styles.item, index > 0 && styles.divided]}>
          {item.accent ? <View style={[styles.dot, { backgroundColor: item.accent }]} /> : null}
          <Text numberOfLines={1} style={styles.value}>{item.value}</Text>
          <Text numberOfLines={1} style={styles.label}>{item.label}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  divided: {
    borderRightColor: fiticianTokens.colors.line,
    borderRightWidth: 1,
  },
  dot: {
    borderRadius: fiticianTokens.radii.pill,
    height: 6,
    width: 6,
  },
  item: {
    alignItems: "center",
    flex: 1,
    gap: 3,
    minWidth: 0,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[3],
  },
  label: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    textAlign: "center",
    writingDirection: "rtl",
  },
  strip: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flexDirection: "row-reverse",
    overflow: "hidden",
  },
  value: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "center",
    writingDirection: "rtl",
  },
});
