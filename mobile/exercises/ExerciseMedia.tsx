import type { components } from "@fitician/core";
import { useIsFocused } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";

import { getMobileRuntimeConfig } from "../config/nativeRuntimeConfig";
import { AppIcon, Media } from "../ui/components";
import { fiticianTokens } from "../ui/tokens";
import {
  exerciseVideoPosterPath,
  isExerciseMediaRenderable,
  resolveExerciseMediaUrl,
} from "./exerciseMedia";

export interface ExerciseMediaProps {
  readonly accessibilityLabel: string;
  readonly autoplay?: boolean;
  readonly compact?: boolean;
  readonly deferVideo?: boolean;
  readonly mediaType: components["schemas"]["MediaType"];
  readonly name: string;
  readonly path: string;
  readonly style?: StyleProp<ViewStyle>;
  readonly videoActive?: boolean;
}

export function ExerciseMedia({
  accessibilityLabel,
  autoplay = false,
  compact = false,
  deferVideo = false,
  mediaType,
  name,
  path,
  style,
  videoActive = false,
}: ExerciseMediaProps) {
  const isFocused = useIsFocused();
  const runtime = getMobileRuntimeConfig();
  const source = { uri: resolveExerciseMediaUrl(path, runtime.apiBaseUrl) };
  const [posterFailed, setPosterFailed] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setPosterFailed(false);
    setVideoFailed(false);
    setLoading(true);
  }, [mediaType, path]);

  const renderable = isExerciseMediaRenderable(path, mediaType);
  const deferredVideo = renderable && mediaType === "video" && deferVideo;
  const posterPath = deferredVideo ? exerciseVideoPosterPath(path) : null;
  const showPoster = deferredVideo
    && (!videoActive || videoFailed)
    && posterPath !== null
    && !posterFailed;
  const mediaMounted = renderable
    && !videoFailed
    && (!deferredVideo || videoActive)
    && (mediaType !== "video" || isFocused);

  return (
    <View accessibilityLabel={accessibilityLabel} accessibilityRole="image" style={[styles.frame, compact && styles.compactFrame, style]}>
      {mediaMounted ? (
        mediaType === "video" ? (
          <Media
            accessibilityLabel={`ویدئوی حرکت ${name}`}
            autoplay={autoplay}
            contentFit="cover"
            kind="video"
            loop
            onError={() => {
              setVideoFailed(true);
              setLoading(false);
            }}
            onFirstFrameRender={() => setLoading(false)}
            source={source}
            style={[styles.media, compact && styles.compactMedia]}
          />
        ) : (
          <Media
            accessibilityLabel={`تصویر حرکت ${name}`}
            onError={() => {
              setVideoFailed(true);
              setLoading(false);
            }}
            onLoad={() => setLoading(false)}
            onLoadStart={() => setLoading(true)}
            source={source}
            style={[styles.media, compact && styles.compactMedia]}
          />
        )
      ) : showPoster ? (
        <Media
          accessibilityLabel={`پوستر حرکت ${name}`}
          onError={() => setPosterFailed(true)}
          source={{ uri: resolveExerciseMediaUrl(posterPath, runtime.apiBaseUrl) }}
          style={[styles.media, compact && styles.compactMedia]}
        />
      ) : !renderable || posterFailed || videoFailed ? (
        <View style={styles.fallback}>
          <AppIcon color={fiticianTokens.colors.aqua} name="training" size={fiticianTokens.iconSize.xl} />
          <Text style={styles.fallbackText}>نمایش حرکت آماده نیست</Text>
        </View>
      ) : null}
      {mediaMounted && loading ? (
        <View pointerEvents="none" style={styles.loadingOverlay}>
          <ActivityIndicator accessibilityLabel="در حال بارگذاری رسانه حرکت" color={fiticianTokens.colors.aqua} />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  compactFrame: {
    minHeight: 0,
  },
  compactMedia: {
    minHeight: 0,
  },
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
  loadingOverlay: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.mediaOverlay,
    bottom: 0,
    justifyContent: "center",
    left: 0,
    position: "absolute",
    right: 0,
    top: 0,
  },
  media: {
    flex: 1,
    minHeight: 160,
  },
});
