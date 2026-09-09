import { useMemo, useRef, useState } from "react";
import {
  PanResponder,
  StyleSheet,
  Text,
  View,
  type LayoutChangeEvent,
} from "react-native";

import { AppIcon, Media } from "../ui/components";
import type { MobileLanguage } from "../ui/rtl";
import { fiticianTokens } from "../ui/tokens";
import {
  isExerciseMediaRenderable,
  resolveExerciseMediaUrl,
  type ExerciseMediaItem,
} from "./exerciseMedia";
import {
  clampMediaIndex,
  MEDIA_SWIPE_THRESHOLD,
  resolveMediaSwipeIndex,
} from "./exerciseMediaCarousel";

export interface ExerciseMediaCarouselProps {
  readonly apiBaseUrl: string;
  readonly items: readonly ExerciseMediaItem[];
  readonly language: MobileLanguage;
  readonly name: string;
  readonly onIndexChange: (index: number) => void;
  readonly selectedIndex: number;
}

const mediaUnavailableCopy: Record<MobileLanguage, string> = {
  en: "Exercise media is unavailable.",
  fa: "رسانهٔ این حرکت در دسترس نیست.",
};

export function ExerciseMediaCarousel({
  apiBaseUrl,
  items,
  language,
  name,
  onIndexChange,
  selectedIndex,
}: ExerciseMediaCarouselProps) {
  const safeIndex = clampMediaIndex(selectedIndex, items.length);
  const item = items[safeIndex];
  const currentIndexRef = useRef(safeIndex);
  const itemCountRef = useRef(items.length);
  const onIndexChangeRef = useRef(onIndexChange);
  const surfaceHeightRef = useRef(0);
  const gestureStartRef = useRef<{ readonly startedInControls: boolean } | null>(null);

  currentIndexRef.current = safeIndex;
  itemCountRef.current = items.length;
  onIndexChangeRef.current = onIndexChange;

  const panResponder = useMemo(() => PanResponder.create({
    onMoveShouldSetPanResponder: (_event, gestureState) => {
      const startedInControls = gestureStartRef.current?.startedInControls ?? false;
      if (startedInControls || itemCountRef.current <= 1) return false;
      return Math.abs(gestureState.dx) >= MEDIA_SWIPE_THRESHOLD
        && Math.abs(gestureState.dx) > Math.abs(gestureState.dy) * 1.2;
    },
    onPanResponderRelease: (_event, gestureState) => {
      const startedInControls = gestureStartRef.current?.startedInControls ?? false;
      gestureStartRef.current = null;
      const nextIndex = resolveMediaSwipeIndex(
        currentIndexRef.current,
        gestureState.dx,
        gestureState.dy,
        itemCountRef.current,
        startedInControls,
      );
      if (nextIndex !== currentIndexRef.current) onIndexChangeRef.current(nextIndex);
    },
    onPanResponderTerminate: () => {
      gestureStartRef.current = null;
    },
    onStartShouldSetPanResponder: (event) => {
      const height = surfaceHeightRef.current;
      gestureStartRef.current = {
        startedInControls: height > 0 && event.nativeEvent.locationY >= height - 64,
      };
      return false;
    },
  }), []);

  function handleLayout(event: LayoutChangeEvent) {
    surfaceHeightRef.current = event.nativeEvent.layout.height;
  }

  return (
    <View
      {...panResponder.panHandlers}
      onLayout={handleLayout}
      style={styles.surface}
      testID="exercise-media-surface"
    >
      {item !== undefined && isExerciseMediaRenderable(item.mediaPath, item.mediaType) ? (
        <NativeExerciseMedia item={item} key={item.key} language={language} name={name} apiBaseUrl={apiBaseUrl} />
      ) : (
        <MediaFallback language={language} />
      )}
      {items.length > 1 ? (
        <View
          accessible
          accessibilityLabel={`${safeIndex + 1}/${items.length}`}
          pointerEvents="none"
          style={styles.indicator}
        >
          <Text style={styles.indicatorText}>{`${safeIndex + 1}/${items.length}`}</Text>
        </View>
      ) : null}
    </View>
  );
}

function NativeExerciseMedia({
  apiBaseUrl,
  item,
  language,
  name,
}: {
  readonly apiBaseUrl: string;
  readonly item: ExerciseMediaItem;
  readonly language: MobileLanguage;
  readonly name: string;
}) {
  const [failed, setFailed] = useState(false);
  const source = { uri: resolveExerciseMediaUrl(item.mediaPath, apiBaseUrl) };
  const accessibilityLabel = language === "en" ? `Exercise demonstration: ${name}` : `نمایش حرکت ${name}`;
  if (failed) return <MediaFallback language={language} />;

  if (item.mediaType === "video") {
    return (
      <Media
        accessibilityLabel={accessibilityLabel}
        contentFit="contain"
        kind="video"
        nativeControls
        onError={() => setFailed(true)}
        source={source}
        style={styles.media}
      />
    );
  }
  return (
    <Media
      accessibilityLabel={accessibilityLabel}
      onError={() => setFailed(true)}
      source={source}
      style={styles.media}
    />
  );
}

function MediaFallback({ language }: { readonly language: MobileLanguage }) {
  return (
    <View accessibilityRole="image" style={styles.mediaFallback}>
      <AppIcon color={fiticianTokens.colors.aqua} name="training" size={fiticianTokens.iconSize.xl} />
      <Text style={[styles.mediaFallbackText, language === "en" && styles.mediaFallbackTextEnglish]}>
        {mediaUnavailableCopy[language]}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  indicator: {
    backgroundColor: fiticianTokens.colors.mediaOverlay,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    paddingHorizontal: 9,
    paddingVertical: 4,
    position: "absolute",
    right: 12,
    top: 12,
  },
  indicatorText: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
  },
  media: {
    height: "100%",
    width: "100%",
  },
  mediaFallback: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    height: "100%",
    justifyContent: "center",
    padding: fiticianTokens.spacing[5],
    width: "100%",
  },
  mediaFallbackText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    textAlign: "center",
    writingDirection: "rtl",
  },
  mediaFallbackTextEnglish: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    writingDirection: "ltr",
  },
  surface: {
    aspectRatio: 4 / 3,
    backgroundColor: fiticianTokens.colors.canvas,
    overflow: "hidden",
    width: "100%",
  },
});
