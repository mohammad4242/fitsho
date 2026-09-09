import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";

import { fiticianTokens } from "../tokens";
import { Skeleton } from "./Feedback";

export interface StateSkeletonProps {
  readonly style?: StyleProp<ViewStyle>;
  readonly variant?: "card" | "hero" | "row";
}

export function StateSkeleton({ style, variant = "card" }: StateSkeletonProps) {
  if (variant === "row") {
    return (
      <View accessibilityLabel="در حال بارگذاری" style={[styles.row, style]}>
        <Skeleton height={76} width={92} />
        <View style={styles.rowCopy}>
          <Skeleton height={18} width="72%" />
          <Skeleton height={12} width="46%" />
        </View>
      </View>
    );
  }

  return (
    <View accessibilityLabel="در حال بارگذاری" style={[styles.card, variant === "hero" && styles.hero, style]}>
      <Skeleton height={variant === "hero" ? 170 : 110} />
      <Skeleton height={20} width="64%" />
      <Skeleton height={13} width="42%" />
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.card,
    borderWidth: 1,
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[4],
  },
  hero: {
    borderRadius: fiticianTokens.radii.extraLarge,
  },
  row: {
    alignItems: "center",
    borderBottomColor: fiticianTokens.colors.line,
    borderBottomWidth: 1,
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[3],
  },
  rowCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[2],
  },
});
