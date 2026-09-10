import { type ReactNode } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  View,
  useWindowDimensions,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import {
  SafeAreaView,
  useSafeAreaInsets,
  type Edges,
} from "react-native-safe-area-context";

import { getResponsiveLayout } from "../layoutMetrics";
import { RTL_LAYOUT } from "../rtl";
import { fiticianTokens } from "../tokens";

export type ScreenContentWidth = "content" | "full" | "reading";

export interface ScreenProps {
  readonly children: ReactNode;
  readonly contentContainerStyle?: StyleProp<ViewStyle>;
  readonly contentWidth?: ScreenContentWidth;
  readonly edges?: Edges;
  readonly keyboardAware?: boolean;
  readonly keyboardVerticalOffset?: number;
  readonly scroll?: boolean;
  readonly style?: StyleProp<ViewStyle>;
}

export function Screen({
  children,
  contentContainerStyle,
  contentWidth = "content",
  edges = ["top", "bottom"],
  keyboardAware = true,
  keyboardVerticalOffset,
  scroll = true,
  style,
}: ScreenProps) {
  const { height, width } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const responsive = getResponsiveLayout(width, height);
  const maxWidth = contentWidth === "full"
    ? undefined
    : contentWidth === "reading"
      ? responsive.readingMaxWidth
      : responsive.contentMaxWidth;
  const contentStyle = [
    styles.content,
    RTL_LAYOUT,
    {
      maxWidth,
      paddingHorizontal: responsive.horizontalPadding,
    },
    contentContainerStyle,
  ];
  const body = scroll ? (
    <ScrollView
      contentContainerStyle={[styles.scrollContent, contentStyle]}
      keyboardDismissMode="on-drag"
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
      style={RTL_LAYOUT}
    >
      {children}
    </ScrollView>
  ) : (
    <View style={contentStyle}>{children}</View>
  );

  return (
    <SafeAreaView edges={edges} style={[styles.safeArea, RTL_LAYOUT, style]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        enabled={keyboardAware}
        keyboardVerticalOffset={keyboardVerticalOffset ?? insets.top}
        style={[styles.keyboard, RTL_LAYOUT]}
      >
        {body}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  content: {
    alignItems: "stretch",
    alignSelf: "center",
    flexGrow: 1,
    width: "100%",
  },
  keyboard: {
    flex: 1,
  },
  safeArea: {
    backgroundColor: fiticianTokens.colors.canvas,
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
  },
});
