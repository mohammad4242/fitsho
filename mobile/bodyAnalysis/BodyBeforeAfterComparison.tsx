import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Image,
  PanResponder,
  Pressable,
  StyleSheet,
  Text,
  View,
  type LayoutChangeEvent,
} from "react-native";

import type { BodyPhoto, BodyPhotoView } from "@fitician/core/body-photos";

import type { PrivateBodyPhotoUris } from "./bodyPhotoPrivateMedia";
import { fiticianTokens } from "../ui/tokens";

const views: readonly BodyPhotoView[] = ["front", "side", "back"];

export function BodyBeforeAfterComparison({
  afterPhotoUris,
  afterPhotos,
  beforePhotoUris,
  beforePhotos,
  currentDate,
  previousDate,
}: {
  readonly afterPhotoUris: PrivateBodyPhotoUris;
  readonly afterPhotos: readonly BodyPhoto[];
  readonly beforePhotoUris: PrivateBodyPhotoUris;
  readonly beforePhotos: readonly BodyPhoto[];
  readonly currentDate: string;
  readonly previousDate: string;
}) {
  const availableViews = useMemo(
    () => views.filter((view) => (
      beforePhotos.some((photo) => photo.view === view) || afterPhotos.some((photo) => photo.view === view)
    )),
    [afterPhotos, beforePhotos],
  );
  const [view, setView] = useState<BodyPhotoView>(availableViews[0] ?? "front");
  const [position, setPosition] = useState(50);
  const stageWidth = useRef(1);

  useEffect(() => {
    if (availableViews.includes(view)) return;
    setView(availableViews[0] ?? "front");
  }, [availableViews, view]);

  const updatePosition = useCallback((locationX: number) => {
    setPosition(Math.min(100, Math.max(0, Math.round((locationX / stageWidth.current) * 100))));
  }, []);

  const panResponder = useMemo(() => PanResponder.create({
    onMoveShouldSetPanResponder: () => true,
    onPanResponderGrant: (event) => updatePosition(event.nativeEvent.locationX),
    onPanResponderMove: (event) => updatePosition(event.nativeEvent.locationX),
    onStartShouldSetPanResponder: () => true,
  }), [updatePosition]);

  const beforePhoto = beforePhotos.find((photo) => photo.view === view);
  const afterPhoto = afterPhotos.find((photo) => photo.view === view);
  const beforeUri = beforePhotoUris[view];
  const afterUri = afterPhotoUris[view];

  function handleStageLayout(event: LayoutChangeEvent) {
    stageWidth.current = Math.max(1, event.nativeEvent.layout.width);
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View style={styles.headerCopy}>
          <Text style={styles.eyebrow}>گذار تصویری</Text>
          <Text accessibilityRole="header" style={styles.title}>قبل و بعد</Text>
        </View>
        <Text style={styles.notice}>مشاهدهٔ تصویری از عکس‌های استاندارد؛ اندازه‌گیری مستقیم اندازهٔ عضله نیست.</Text>
      </View>
      <View accessibilityLabel="نمای مقایسهٔ قبل و بعد" style={styles.views}>
        {availableViews.map((nextView) => (
          <Pressable
            accessibilityLabel={viewLabel(nextView)}
            accessibilityRole="button"
            accessibilityState={{ selected: view === nextView }}
            key={nextView}
            onPress={() => setView(nextView)}
            style={[styles.viewButton, view === nextView && styles.viewButtonSelected]}
          >
            <Text style={[styles.viewButtonText, view === nextView && styles.viewButtonTextSelected]}>
              {viewLabel(nextView)}
            </Text>
          </Pressable>
        ))}
      </View>
      <View
        accessibilityLabel="موقعیت مقایسهٔ قبل و بعد"
        accessibilityRole="adjustable"
        accessibilityValue={{ max: 100, min: 0, now: position }}
        onLayout={handleStageLayout}
        style={styles.stage}
        {...panResponder.panHandlers}
      >
        {beforeUri !== undefined && afterUri !== undefined ? (
          <>
            <Image accessibilityIgnoresInvertColors source={{ uri: beforeUri }} style={styles.stageImage} />
            <View style={[styles.afterLayer, { width: `${100 - position}%` }]}>
              <Image accessibilityIgnoresInvertColors source={{ uri: afterUri }} style={styles.stageImage} />
            </View>
            <View style={[styles.divider, { left: `${position}%` }]} />
            <View style={[styles.photoLabel, styles.beforeLabel]}>
              <Text style={styles.photoLabelTitle}>قبل</Text>
              <Text style={styles.photoLabelDate}>{previousDate}</Text>
            </View>
            <View style={[styles.photoLabel, styles.afterLabel]}>
              <Text style={styles.photoLabelTitle}>بعد</Text>
              <Text style={styles.photoLabelDate}>{currentDate}</Text>
            </View>
          </>
        ) : (
          <Text style={styles.unavailable}>جفت عکس نمای {viewLabel(view)} برای این مقایسه در دسترس نیست.</Text>
        )}
      </View>
      <View style={styles.sliderSummary}>
        <Text style={styles.muted}>میزان نمایش</Text>
        <View style={styles.sliderTrack}>
          <View style={[styles.sliderFill, { width: `${position}%` }]} />
        </View>
        <Text style={styles.muted}>{formatCount(position)}٪</Text>
      </View>
      {beforePhoto !== undefined && afterPhoto !== undefined && (beforeUri === undefined || afterUri === undefined) ? (
        <Text style={styles.privateNotice}>در حال دریافت نسخهٔ خصوصی عکس‌ها…</Text>
      ) : null}
    </View>
  );
}

function formatCount(value: number): string {
  return new Intl.NumberFormat("fa-IR").format(value);
}

function viewLabel(view: BodyPhotoView): string {
  if (view === "front") return "روبه‌رو";
  if (view === "side") return "نیمرخ";
  return "پشت";
}

const styles = StyleSheet.create({
  afterLabel: {
    right: 10,
    textAlign: "right",
  },
  afterLayer: {
    bottom: 0,
    overflow: "hidden",
    position: "absolute",
    right: 0,
    top: 0,
  },
  beforeLabel: {
    left: 10,
  },
  container: {
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.extraLarge,
    borderWidth: 1,
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[3],
  },
  divider: {
    backgroundColor: "#ffffff",
    bottom: 0,
    position: "absolute",
    shadowColor: "#000000",
    shadowOpacity: 0.45,
    shadowRadius: 6,
    top: 0,
    width: 2,
  },
  eyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  header: {
    gap: fiticianTokens.spacing[2],
  },
  headerCopy: {
    gap: fiticianTokens.spacing[1],
  },
  muted: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  notice: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 19,
    textAlign: "right",
    writingDirection: "rtl",
  },
  photoLabel: {
    backgroundColor: "rgba(1,10,12,0.72)",
    borderRadius: fiticianTokens.radii.small,
    bottom: 10,
    gap: 2,
    paddingHorizontal: 8,
    paddingVertical: 6,
    position: "absolute",
  },
  photoLabelDate: {
    color: "rgba(255,255,255,0.78)",
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    textAlign: "right",
    writingDirection: "rtl",
  },
  photoLabelTitle: {
    color: "#ffffff",
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  privateNotice: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  sliderFill: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    height: "100%",
  },
  sliderSummary: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[2],
  },
  sliderTrack: {
    backgroundColor: fiticianTokens.colors.progressTrack,
    borderRadius: fiticianTokens.radii.pill,
    flex: 1,
    height: 8,
    overflow: "hidden",
  },
  stage: {
    aspectRatio: 1 / 1.25,
    backgroundColor: fiticianTokens.colors.canvas,
    borderRadius: fiticianTokens.radii.large,
    direction: "ltr",
    overflow: "hidden",
    position: "relative",
    width: "100%",
  },
  stageImage: {
    bottom: 0,
    height: "100%",
    left: 0,
    position: "absolute",
    right: 0,
    top: 0,
    width: "100%",
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "rtl",
  },
  unavailable: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 24,
    margin: "auto",
    padding: fiticianTokens.spacing[4],
    textAlign: "center",
    writingDirection: "rtl",
  },
  viewButton: {
    alignItems: "center",
    borderRadius: fiticianTokens.radii.pill,
    minHeight: 42,
    paddingHorizontal: fiticianTokens.spacing[3],
  },
  viewButtonSelected: {
    backgroundColor: fiticianTokens.colors.aqua,
  },
  viewButtonText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "center",
    writingDirection: "rtl",
  },
  viewButtonTextSelected: {
    color: fiticianTokens.colors.canvas,
  },
  views: {
    alignSelf: "flex-start",
    backgroundColor: fiticianTokens.colors.canvas,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    flexDirection: "row-reverse",
    gap: 2,
    padding: 2,
  },
});
