import type { components } from "@fitician/core";
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";

import { getMobileRuntimeConfig } from "../config/nativeRuntimeConfig";
import { AppIcon, Media } from "../ui/components";
import { fiticianTokens } from "../ui/tokens";
import { isExerciseMediaRenderable, resolveExerciseMediaUrl } from "./exerciseMedia";

export interface ExerciseMediaProps {
  readonly accessibilityLabel: string;
  readonly autoplay?: boolean;
  readonly mediaType: components["schemas"]["MediaType"];
  readonly name: string;
  readonly path: string;
  readonly style?: StyleProp<ViewStyle>;
}

export function ExerciseMedia({
  accessibilityLabel,
  autoplay = false,
  mediaType,
  name,
  path,
  style,
}: ExerciseMediaProps) {
  const runtime = getMobileRuntimeConfig();
  const source = { uri: resolveExerciseMediaUrl(path, runtime.apiBaseUrl) };

  return (
    <View accessibilityLabel={accessibilityLabel} accessibilityRole="image" style={[styles.frame, style]}>
      {isExerciseMediaRenderable(path, mediaType) ? (
        mediaType === "video" ? (
          <Media
            accessibilityLabel={`ویدئوی حرکت ${name}`}
            autoplay={autoplay}
            contentFit="cover"
            kind="video"
            loop
            source={source}
            style={styles.media}
          />
        ) : (
          <Media
            accessibilityLabel={`تصویر حرکت ${name}`}
            source={source}
            style={styles.media}
          />
        )
      ) : (
        <View style={styles.fallback}>
          <AppIcon color={fiticianTokens.colors.aqua} name="training" size={fiticianTokens.iconSize.xl} />
          <Text style={styles.fallbackText}>نمایش حرکت آماده نیست</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  fallback: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    flex: 1,
    gap: fiticianTokens.spacing[2],
    justifyContent: "center",
    minHeight: 160,
    padding: fiticianTokens.spacing[4],
  },
  fallbackText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "center",
    writingDirection: "rtl",
  },
  frame: {
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderRadius: fiticianTokens.radii.large,
    minHeight: 160,
    overflow: "hidden",
  },
  media: {
    flex: 1,
    minHeight: 160,
  },
});
