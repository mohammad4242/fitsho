import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  type AccessibilityState,
  type StyleProp,
  type ViewStyle,
} from "react-native";

import { fiticianTokens } from "../tokens";

export type SegmentedControlDirection = "rtl" | "ltr";

export interface SegmentedControlOption {
  readonly label: string;
  readonly value: string;
}

export interface SegmentedControlProps {
  readonly accessibilityLabel?: string;
  readonly direction?: SegmentedControlDirection;
  readonly disabled?: boolean;
  readonly loading?: boolean;
  readonly onChange: (value: string) => void;
  readonly options: readonly SegmentedControlOption[];
  readonly selectedValue: string;
  readonly style?: StyleProp<ViewStyle>;
  readonly testID?: string;
}

export function SegmentedControl({
  accessibilityLabel,
  direction = "rtl",
  disabled = false,
  loading = false,
  onChange,
  options,
  selectedValue,
  style,
  testID = "segmented-control",
}: SegmentedControlProps) {
  const unavailable = disabled || loading;

  return (
    <View
      accessibilityLabel={accessibilityLabel}
      accessibilityRole="radiogroup"
      style={[styles.container, { direction, flexDirection: "row" }, style]}
      testID={testID}
    >
      {options.map((option) => {
        const selected = option.value === selectedValue;
        const accessibilityState: AccessibilityState = {
          busy: loading,
          disabled: unavailable,
          selected,
        };

        return (
          <Pressable
            accessibilityLabel={option.label}
            accessibilityRole="radio"
            accessibilityState={accessibilityState}
            disabled={unavailable}
            key={option.value}
            onPress={() => {
              if (!unavailable && !selected) onChange(option.value);
            }}
            style={[styles.option, selected && styles.selectedOption, unavailable && styles.disabledOption]}
          >
            <Text
              allowFontScaling
              style={[styles.label, selected && styles.selectedLabel, { writingDirection: direction }]}
            >
              {option.label}
            </Text>
            {loading && selected ? (
              <ActivityIndicator accessibilityLabel="در حال بارگذاری" color={fiticianTokens.colors.aqua} size="small" />
            ) : null}
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderRadius: fiticianTokens.radii.medium,
    gap: fiticianTokens.spacing[1],
    overflow: "hidden",
    width: "100%",
  },
  disabledOption: {
    opacity: 0.52,
  },
  label: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "center",
  },
  option: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flex: 1,
    justifyContent: "center",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    minWidth: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  selectedLabel: {
    color: fiticianTokens.colors.aqua,
  },
  selectedOption: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.aqua,
  },
});
