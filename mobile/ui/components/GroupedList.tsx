import { type ReactNode } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  View,
  type AccessibilityState,
  type StyleProp,
  type ViewStyle,
} from "react-native";

import type { FiticianIconName } from "../icons";
import { fiticianTokens } from "../tokens";
import { AppIcon } from "./AppIcon";

export type GroupedListDirection = "rtl" | "ltr";

export interface GroupedListItem {
  readonly accessibilityHint?: string;
  readonly accessibilityLabel?: string;
  readonly disabled?: boolean;
  readonly icon?: FiticianIconName;
  readonly label: string;
  readonly onPress?: () => void;
  readonly subtitle?: string;
  readonly trailing?: ReactNode;
}

export interface GroupedListSection {
  readonly items: readonly GroupedListItem[];
  readonly title?: string;
}

export interface GroupedListProps {
  readonly direction?: GroupedListDirection;
  readonly sections: readonly GroupedListSection[];
  readonly style?: StyleProp<ViewStyle>;
  readonly testID?: string;
}

export function GroupedList({ direction = "rtl", sections, style, testID }: GroupedListProps) {
  const isRtl = direction === "rtl";

  return (
    <View
      style={[styles.container, { direction }, style]}
      testID={testID}
    >
      {sections.map((section, sectionIndex) => (
        <View key={`${section.title ?? "section"}-${sectionIndex}`}>
          {section.title ? (
            <Text
              accessibilityRole="header"
              style={[styles.sectionTitle, { textAlign: isRtl ? "right" : "left", writingDirection: direction }]}
            >
              {section.title}
            </Text>
          ) : null}
          {section.items.map((item, itemIndex) => {
            const unavailable = item.disabled === true;
            const rowStyle: StyleProp<ViewStyle> = [
              styles.row,
              itemIndex > 0 && styles.divided,
              unavailable && styles.disabledRow,
            ];
            const content = (
              <>
                {item.icon ? <AppIcon color={fiticianTokens.colors.aqua} name={item.icon} /> : null}
                <View style={styles.copy}>
                  <Text
                    allowFontScaling
                    numberOfLines={2}
                    style={[styles.label, { textAlign: isRtl ? "right" : "left", writingDirection: direction }]}
                  >
                    {item.label}
                  </Text>
                  {item.subtitle ? (
                    <Text
                      allowFontScaling
                      numberOfLines={2}
                      style={[styles.subtitle, { textAlign: isRtl ? "right" : "left", writingDirection: direction }]}
                    >
                      {item.subtitle}
                    </Text>
                  ) : null}
                </View>
                {item.trailing ?? null}
              </>
            );

            if (!item.onPress) {
              return <View key={`${item.label}-${itemIndex}`} style={rowStyle}>{content}</View>;
            }

            const accessibilityState: AccessibilityState = { disabled: unavailable };
            return (
              <Pressable
                accessibilityHint={item.accessibilityHint}
                accessibilityLabel={item.accessibilityLabel ?? item.label}
                accessibilityRole="button"
                accessibilityState={accessibilityState}
                disabled={unavailable}
                key={`${item.label}-${itemIndex}`}
                onPress={item.onPress}
                style={({ pressed }) => [rowStyle, pressed && styles.pressed]}
              >
                {content}
              </Pressable>
            );
          })}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    overflow: "hidden",
    width: "100%",
  },
  copy: {
    alignItems: "stretch",
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
  },
  disabledRow: {
    opacity: 0.52,
  },
  divided: {
    borderTopColor: fiticianTokens.colors.line,
    borderTopWidth: 1,
  },
  label: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.medium,
    lineHeight: 24,
  },
  pressed: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
  },
  row: {
    alignItems: "center",
    gap: fiticianTokens.spacing[3],
    flexDirection: "row",
    minHeight: 68,
    paddingHorizontal: fiticianTokens.spacing[4],
    paddingVertical: fiticianTokens.spacing[3],
    width: "100%",
  },
  sectionTitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    paddingHorizontal: fiticianTokens.spacing[4],
    paddingTop: fiticianTokens.spacing[4],
    textTransform: "none",
  },
  subtitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 18,
  },
});
