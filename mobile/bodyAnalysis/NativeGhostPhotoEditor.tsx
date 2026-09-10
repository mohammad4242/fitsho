import { useMemo, useRef, useState } from "react";
import {
  Image,
  PanResponder,
  StyleSheet,
  Text,
  View,
  type GestureResponderEvent,
  type LayoutChangeEvent,
} from "react-native";

import type { BodyPhotoSide, BodyPhotoView } from "@fitician/core/body-photos";
import {
  GHOST_SCALE_MAX,
  GHOST_SCALE_MIN,
  GHOST_SCALE_STEP,
  PHOTO_SCALE_MAX,
  PHOTO_SCALE_MIN,
  PHOTO_SCALE_STEP,
  stepGhostScale,
} from "@fitician/core/body-ghost-scale";
import {
  GHOST_EDITOR_DEFAULT_TRANSFORM,
  clampGhostPhotoTransform,
  isGhostFramingWithinTolerance,
} from "@fitician/core/body-ghost-editor";
import type { GhostPhotoTransform } from "@fitician/core/body-ghost-editor";
import type { Sex } from "@fitician/core/profile";

import { Button, Notice } from "../ui/components";
import { fiticianTokens } from "../ui/tokens";
import { bodyPhotoCopy } from "./bodyAnalysisCopy";
import {
  applyGhostPhotoDrag,
  applyGhostPhotoPinchGesture,
  createGhostPhotoPinchGesture,
  type GhostPhotoPinchGesture,
  type GhostPhotoPoint,
  type GhostPhotoStageSize,
} from "./ghostPhotoEditor";
import type { BodyPhotoCapturedAsset } from "./cameraCapture";
import { resolveGhostOverlayVariant } from "./ghostOverlay";
import { GhostOverlayGuide } from "./GhostOverlayGuide";
import { renderNativeGhostPhoto, type NativeGhostPhotoRenderInput } from "./nativeGhostPhotoRenderer";

type GhostPhotoEditorProps = {
  readonly ghostScale: number;
  readonly onCancel: () => void;
  readonly onGhostScaleChange: (scale: number) => void;
  readonly onPrepared: (asset: BodyPhotoCapturedAsset) => void | Promise<void>;
  readonly onPreparedError?: (error: unknown) => string;
  readonly sex?: Sex | null;
  readonly sideProfile?: BodyPhotoSide;
  readonly source: NativeGhostPhotoRenderInput;
  readonly view: BodyPhotoView;
};

type DragState = {
  readonly origin: GhostPhotoTransform;
};

export function NativeGhostPhotoEditor({
  ghostScale,
  onCancel,
  onGhostScaleChange,
  onPrepared,
  onPreparedError = defaultPreparedError,
  sex,
  sideProfile = "right",
  source,
  view,
}: GhostPhotoEditorProps) {
  const [photoTransform, setPhotoTransform] = useState<GhostPhotoTransform>(GHOST_EDITOR_DEFAULT_TRANSFORM);
  const [stageSize, setStageSize] = useState<GhostPhotoStageSize>({ height: 520, width: 320 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const transformRef = useRef(photoTransform);
  const stageSizeRef = useRef(stageSize);
  const dragRef = useRef<DragState | null>(null);
  const pinchRef = useRef<GhostPhotoPinchGesture | null>(null);
  const ghostVariant = resolveGhostOverlayVariant(sex);

  function updatePhotoTransform(update: (current: GhostPhotoTransform) => GhostPhotoTransform) {
    const next = clampGhostPhotoTransform(update(transformRef.current));
    transformRef.current = next;
    setPhotoTransform(next);
  }

  function handleStageLayout(event: LayoutChangeEvent) {
    const { height, width } = event.nativeEvent.layout;
    if (height <= 0 || width <= 0) return;
    const next = { height, width };
    stageSizeRef.current = next;
    setStageSize(next);
  }

  const panResponder = useMemo(() => PanResponder.create({
    onMoveShouldSetPanResponder: () => true,
    onPanResponderGrant: (event) => {
      if (busy) return;
      const points = readTwoTouchPoints(event);
      if (points !== null) {
        pinchRef.current = createGhostPhotoPinchGesture(
          points[0],
          points[1],
          transformRef.current,
          stageSizeRef.current,
        );
        dragRef.current = null;
        return;
      }
      dragRef.current = { origin: transformRef.current };
    },
    onPanResponderMove: (event, gestureState) => {
      if (busy) return;
      const points = readTwoTouchPoints(event);
      if (points !== null) {
        if (pinchRef.current === null) {
          pinchRef.current = createGhostPhotoPinchGesture(
            points[0],
            points[1],
            transformRef.current,
            stageSizeRef.current,
          );
        }
        const next = applyGhostPhotoPinchGesture(pinchRef.current, points[0], points[1]);
        transformRef.current = next;
        setPhotoTransform(next);
        dragRef.current = null;
        return;
      }
      const drag = dragRef.current;
      if (drag === null) return;
      const next = applyGhostPhotoDrag(
        drag.origin,
        { x: gestureState.dx, y: gestureState.dy },
        stageSizeRef.current,
      );
      transformRef.current = next;
      setPhotoTransform(next);
    },
    onPanResponderRelease: () => {
      dragRef.current = null;
      pinchRef.current = null;
    },
    onPanResponderTerminate: () => {
      dragRef.current = null;
      pinchRef.current = null;
    },
    onPanResponderTerminationRequest: () => true,
    onStartShouldSetPanResponder: () => true,
  }), [busy]);

  async function confirmPhoto() {
    if (busy) return;
    setBusy(true);
    setError(null);
    let asset: BodyPhotoCapturedAsset;
    try {
      asset = await renderNativeGhostPhoto({
        ...source,
        ghostScale,
        ghostVariant,
        transform: transformRef.current,
      });
    } catch {
      setError(bodyPhotoCopy.editor.renderError);
      setBusy(false);
      return;
    }
    try {
      await onPrepared(asset);
    } catch (cause) {
      setError(onPreparedError(cause));
    } finally {
      setBusy(false);
    }
  }

  const framingIsWithinTolerance = isGhostFramingWithinTolerance(photoTransform);
  const photoScale = photoTransform.scale;

  return (
    <View style={styles.container}>
      <View style={styles.heading}>
        <Text style={styles.eyebrow}>{bodyPhotoCopy.editor.eyebrow}</Text>
        <Text style={styles.title}>{bodyPhotoCopy.editor.title}</Text>
        <Text style={styles.body}>{replaceView(bodyPhotoCopy.editor.body, viewLabel(view))}</Text>
      </View>
      <View
        accessibilityLabel={bodyPhotoCopy.editor.stageLabel}
        accessible
        onLayout={handleStageLayout}
        style={styles.stage}
        {...panResponder.panHandlers}
      >
        <Image
          accessibilityLabel={replaceView(bodyPhotoCopy.editor.imageAlt, viewLabel(view))}
          resizeMode="contain"
          source={{ uri: source.uri }}
          style={[styles.photo, photoTransformStyle(photoTransform, stageSize)]}
        />
        <GhostOverlayGuide ghostScale={ghostScale} sideProfile={sideProfile} sex={sex} view={view} />
      </View>
      <Text style={styles.privacyNote}>{bodyPhotoCopy.editor.privacyNote}</Text>
      <Text accessibilityLiveRegion="polite" style={styles.status}>
        {framingIsWithinTolerance
          ? bodyPhotoCopy.editor.framingOkay
          : bodyPhotoCopy.editor.framingApproximate}
      </Text>
      <View accessibilityLabel={bodyPhotoCopy.editor.controlsLabel} style={styles.controls}>
        <Text style={styles.controlLabel}>{bodyPhotoCopy.camera.ghostScale.replace("{{percent}}", `${Math.round(ghostScale * 100)}`)}</Text>
        <View style={styles.buttonRow}>
          <Button
            disabled={busy || ghostScale <= GHOST_SCALE_MIN}
            label={bodyPhotoCopy.camera.ghostSmaller}
            onPress={() => onGhostScaleChange(stepGhostScale(ghostScale, -GHOST_SCALE_STEP))}
            variant="secondary"
          />
          <Button
            disabled={busy || ghostScale >= GHOST_SCALE_MAX}
            label={bodyPhotoCopy.camera.ghostLarger}
            onPress={() => onGhostScaleChange(stepGhostScale(ghostScale, GHOST_SCALE_STEP))}
            variant="secondary"
          />
        </View>
        <View style={styles.buttonRow}>
          <Button
            disabled={busy || photoScale <= PHOTO_SCALE_MIN}
            label={bodyPhotoCopy.editor.zoomOut}
            onPress={() => updatePhotoTransform((current) => ({ ...current, scale: current.scale - PHOTO_SCALE_STEP }))}
            variant="secondary"
          />
          <Button
            disabled={busy || photoScale >= PHOTO_SCALE_MAX}
            label={bodyPhotoCopy.editor.zoomIn}
            onPress={() => updatePhotoTransform((current) => ({ ...current, scale: current.scale + PHOTO_SCALE_STEP }))}
            variant="secondary"
          />
        </View>
        <View style={styles.buttonRow}>
          <Button
            disabled={busy}
            label={bodyPhotoCopy.editor.rotateLeft}
            onPress={() => updatePhotoTransform((current) => ({ ...current, rotation: current.rotation - 1 }))}
            variant="secondary"
          />
          <Button
            disabled={busy}
            label={bodyPhotoCopy.editor.rotateRight}
            onPress={() => updatePhotoTransform((current) => ({ ...current, rotation: current.rotation + 1 }))}
            variant="secondary"
          />
        </View>
        <Button
          disabled={busy}
          label={bodyPhotoCopy.editor.reset}
          onPress={() => updatePhotoTransform(() => GHOST_EDITOR_DEFAULT_TRANSFORM)}
          variant="ghost"
        />
      </View>
      {error !== null ? <Notice message={error} variant="danger" /> : null}
      <View style={styles.actions}>
        <Button disabled={busy} label={bodyPhotoCopy.editor.cancel} onPress={onCancel} variant="secondary" />
        <Button
          disabled={busy}
          label={bodyPhotoCopy.editor.confirm}
          loading={busy}
          onPress={() => void confirmPhoto()}
        />
      </View>
    </View>
  );
}

function defaultPreparedError(): string {
  return "ثبت این تصویر انجام نشد. عکس‌های ثبت‌شده حفظ شدند؛ دوباره تلاش کن.";
}

function replaceView(template: string, view: string): string {
  return template.replace("{{view}}", view);
}

function viewLabel(view: BodyPhotoView): string {
  if (view === "front") return "روبه‌رو";
  if (view === "side") return "نیمرخ";
  return "پشت";
}

function photoTransformStyle(
  transform: GhostPhotoTransform,
  stage: GhostPhotoStageSize,
) {
  const safe = clampGhostPhotoTransform(transform);
  return {
    transform: [
      { translateX: safe.translateX * stage.width },
      { translateY: safe.translateY * stage.height },
      { rotate: `${safe.rotation}deg` },
      { scale: safe.scale },
    ],
  } as const;
}

function readTwoTouchPoints(event: GestureResponderEvent): [GhostPhotoPoint, GhostPhotoPoint] | null {
  const touches = event.nativeEvent.touches;
  if (touches.length < 2 || touches[0] === undefined || touches[1] === undefined) return null;
  return [
    { x: touches[0].locationX, y: touches[0].locationY },
    { x: touches[1].locationX, y: touches[1].locationY },
  ];
}

const styles = StyleSheet.create({
  actions: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    justifyContent: "space-between",
  },
  body: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  buttonRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  container: {
    gap: fiticianTokens.spacing[3],
  },
  controlLabel: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  controls: {
    gap: fiticianTokens.spacing[2],
  },
  eyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  heading: {
    gap: fiticianTokens.spacing[1],
  },
  photo: {
    height: "100%",
    position: "absolute",
    width: "100%",
  },
  privacyNote: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  stage: {
    alignSelf: "center",
    aspectRatio: 2 / 3,
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    overflow: "hidden",
    position: "relative",
    width: "100%",
    maxWidth: 400,
  },
  status: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 30,
    textAlign: "auto",
    writingDirection: "rtl",
  },
});
