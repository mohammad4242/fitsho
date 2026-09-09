import { useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";

import { getMobileRuntimeConfig } from "../config/nativeRuntimeConfig";
import { AppIcon, Media } from "../ui/components";
import { fiticianTokens } from "../ui/tokens";

export interface NutritionThumbnailProps {
  readonly imageUrl: string | null | undefined;
  readonly name: string;
  readonly style?: StyleProp<ViewStyle>;
}

export function NutritionThumbnail({ imageUrl, name, style }: NutritionThumbnailProps) {
  const runtime = getMobileRuntimeConfig();
  const normalizedImageUrl = imageUrl?.trim() || null;
  const [failed, setFailed] = useState(normalizedImageUrl === null);
  const [loading, setLoading] = useState(normalizedImageUrl !== null);

  useEffect(() => {
    setFailed(false);
    setLoading(normalizedImageUrl !== null);
  }, [normalizedImageUrl]);

  const resolvedImageUrl = normalizedImageUrl === null
    ? null
    : resolveNutritionImageUrl(normalizedImageUrl, runtime.apiBaseUrl);

  if (resolvedImageUrl === null || failed) {
    return (
      <View accessibilityLabel={`تصویر ${name} موجود نیست`} accessibilityRole="image" style={[styles.frame, style]}>
        <AppIcon color={fiticianTokens.colors.aqua} name="nutrition" size={fiticianTokens.iconSize.lg} />
        <Text style={styles.fallbackText}>تصویر موجود نیست</Text>
      </View>
    );
  }

  return (
    <View style={[styles.frame, style]}>
      <Media
        accessibilityLabel={`تصویر ${name}`}
        onError={() => {
          setFailed(true);
          setLoading(false);
        }}
        onLoad={() => setLoading(false)}
        onLoadStart={() => setLoading(true)}
        source={{ uri: resolvedImageUrl }}
        style={styles.media}
      />
      {loading ? (
        <View pointerEvents="none" style={styles.loadingOverlay}>
          <ActivityIndicator accessibilityLabel="در حال بارگذاری تصویر" color={fiticianTokens.colors.aqua} />
        </View>
      ) : null}
    </View>
  );
}

function resolveNutritionImageUrl(path: string, apiBaseUrl: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return `${apiBaseUrl.replace(/\/+$/u, "")}/${path.replace(/^\/+/, "")}`;
}

const styles = StyleSheet.create({
  fallbackText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "center",
    writingDirection: "rtl",
  },
  frame: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderRadius: fiticianTokens.radii.medium,
    gap: fiticianTokens.spacing[1],
    height: 88,
    justifyContent: "center",
    overflow: "hidden",
    width: 88,
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
    height: "100%",
    width: "100%",
  },
});
