import { useState, type ReactNode } from "react";
import { Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";
import { fiticianTokens as tokens } from "../tokens";
import type { FiticianIconName } from "../icons";
import { AppIcon } from "./AppIcon";
import { Card } from "./Card";

export interface DisclosureCardProps {
  readonly title: string;
  readonly summary?: string;
  readonly icon?: FiticianIconName;
  readonly leading?: ReactNode;
  readonly trailing?: ReactNode;
  readonly children: ReactNode;
  readonly expanded?: boolean;
  readonly defaultExpanded?: boolean;
  readonly direction?: "rtl" | "ltr";
  readonly onExpandedChange?: (expanded: boolean) => void;
  readonly style?: StyleProp<ViewStyle>;
}

export function DisclosureCard({ title, summary, icon, leading, trailing, children,
  expanded, defaultExpanded = false, direction = "rtl", onExpandedChange, style }: DisclosureCardProps) {
  const [open, setOpen] = useState(defaultExpanded);
  const visible = expanded ?? open;
  // Keep visited forms mounted so closing a group cannot discard local edits.
  const [visited, setVisited] = useState(defaultExpanded || expanded === true);
  return (
    <Card style={[styles.card, direction === "ltr" && styles.ltr, style]}>
      <Pressable
        accessibilityLabel={title}
        accessibilityHint={summary}
        accessibilityRole="button"
        accessibilityState={{ expanded: visible }}
        onPress={() => {
          setVisited(true);
          if (expanded === undefined) setOpen(!visible);
          onExpandedChange?.(!visible);
        }}
        style={({ pressed }) => [styles.header, pressed && styles.pressed]}
      >
        {leading ?? (icon ? <AppIcon name={icon} color={tokens.colors.aqua} /> : null)}
        <View style={styles.copy}>
          <Text style={[styles.title, direction === "ltr" && styles.titleLtr]}>{title}</Text>
          {summary ? <Text style={[styles.summary, direction === "ltr" && styles.summaryLtr]}>{summary}</Text> : null}
        </View>
        {trailing}
        <AppIcon name={visible ? "chevronUp" : "chevronDown"} color={tokens.colors.aqua} />
      </Pressable>
      {visible || visited ? (
        <View accessibilityElementsHidden={!visible} importantForAccessibility={visible ? "auto" : "no-hide-descendants"}
          style={[styles.body, !visible && styles.hidden]}>{children}</View>
      ) : null}
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { padding: 0, overflow: "hidden" },
  ltr: { direction: "ltr" },
  header: { minHeight: tokens.layout.minimumTouchTarget, padding: tokens.spacing[3], gap: tokens.spacing[3], flexDirection: "row", alignItems: "center" },
  copy: { alignItems: "stretch", flex: 1, minWidth: 0, gap: tokens.spacing[1] },
  title: { color: tokens.colors.ink, fontFamily: tokens.typography.fontFamily.bodyPersian, fontSize: tokens.typography.fontSize.body, fontWeight: tokens.typography.fontWeight.bold, textAlign: "right", writingDirection: "rtl" },
  titleLtr: { fontFamily: tokens.typography.fontFamily.bodyEnglish, textAlign: "left", writingDirection: "ltr" },
  summary: { color: tokens.colors.muted, fontFamily: tokens.typography.fontFamily.bodyPersian, fontSize: tokens.typography.fontSize.xs, textAlign: "right", writingDirection: "rtl" },
  summaryLtr: { fontFamily: tokens.typography.fontFamily.bodyEnglish, textAlign: "left", writingDirection: "ltr" },
  body: { padding: tokens.spacing[4], gap: tokens.spacing[3], borderTopWidth: 1, borderTopColor: tokens.colors.line },
  hidden: { display: "none" },
  pressed: { opacity: 0.8 },
});
