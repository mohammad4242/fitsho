import { Pressable, StyleSheet, Text, View, type ColorValue } from "react-native";

import { fiticianTokens } from "../tokens";

export interface BrandMarkProps {
  readonly accessibilityLabel?: string;
  readonly color?: ColorValue;
  readonly label: string;
  readonly onPress?: () => void;
  readonly testID?: string;
}

export function BrandMark({ accessibilityLabel, color, label, onPress, testID }: BrandMarkProps) {
  const brandColor = color ?? fiticianTokens.colors.mist;
  const content = (
    <>
      <View style={[styles.pulse, { borderColor: brandColor }]} testID={testID ? `${testID}-pulse` : undefined}>
        <View style={styles.pulseLine} />
      </View>
      <Text style={[styles.label, { color: brandColor }]}>{label}</Text>
    </>
  );

  if (onPress !== undefined) {
    return (
      <Pressable
        accessibilityLabel={accessibilityLabel ?? label}
        accessibilityRole="link"
        onPress={onPress}
        style={styles.mark}
        testID={testID}
      >
        {content}
      </Pressable>
    );
  }

  return (
    <View accessible accessibilityLabel={accessibilityLabel ?? label} style={styles.mark} testID={testID}>
      {content}
    </View>
  );
}

const styles = StyleSheet.create({
  label: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 22,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    writingDirection: "rtl",
  },
  mark: {
    alignItems: "center",
    flexDirection: "row",
    gap: 10,
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: 4,
  },
  pulse: {
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 5,
    height: 26,
    position: "relative",
    width: 26,
  },
  pulseLine: {
    backgroundColor: fiticianTokens.colors.coral,
    height: 3,
    left: -6,
    position: "absolute",
    top: 8,
    transform: [{ rotate: "-20deg" }],
    width: 38,
  },
});
