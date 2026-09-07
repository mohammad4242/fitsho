import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Camera,
  useCameraDevice,
  useCameraPermission,
  useFrameOutput,
  usePhotoOutput,
} from "react-native-vision-camera";
import { scheduleOnRN } from "react-native-worklets";
import { File } from "expo-file-system";
import * as ImagePicker from "expo-image-picker";
import {
  Image,
  StyleSheet,
  Text,
  View,
  type ImageSourcePropType,
} from "react-native";
import type { NativeBodyVisionResult } from "@fitician/body-vision";
import type { GhostPoseValidationResult } from "@fitician/core/body-ghost-pose";
import type { BodyPhotoSide, BodyPhotoView } from "@fitician/core/body-photos";
import type { Sex } from "@fitician/core/profile";

import { useAndroidBackHandler } from "../ui/navigation/BackBehaviorProvider";
import { Button, Notice } from "../ui/components";
import { fiticianTokens } from "../ui/tokens";
import {
  GHOST_SCALE_MAX,
  GHOST_SCALE_MIN,
  GHOST_SCALE_STEP,
  stepGhostScale,
} from "@fitician/core/body-ghost-scale";
import { getNativeBodyVision, validateNativeBodyVisionResult } from "./nativeBodyVision";
import { GhostOverlayGuide } from "./GhostOverlayGuide";
import {
  BODY_PHOTO_COUNTDOWN_SECONDS,
  advanceBodyPhotoCountdown,
  bodyPhotoCaptureErrorMessage,
  bodyPhotoMimeTypeForAsset,
  filePathToUri,
  type BodyPhotoCapturedAsset,
} from "./cameraCapture";

export interface BodyPhotoCaptureProps {
  readonly initialCaptureMode?: "camera" | "library";
  readonly initialGhostScale?: number;
  readonly initialSideProfile?: BodyPhotoSide;
  readonly onCancel: () => void;
  readonly onCaptured: (asset: BodyPhotoCapturedAsset) => void | Promise<void>;
  readonly onGhostScaleChange?: (scale: number) => void;
  readonly onSideProfileChange?: (sideProfile: BodyPhotoSide) => void;
  readonly sex?: Sex | null;
  readonly view: BodyPhotoView;
}

type CameraPosition = "front" | "back";
type LiveStatus = "available" | "unavailable" | "loading";
type LiveWarning =
  | "person_missing"
  | "multiple_people"
  | "body_out_of_frame"
  | "too_close"
  | "too_far"
  | "wrong_view";

export function BodyPhotoCapture({
  initialCaptureMode = "camera",
  initialGhostScale = 1,
  initialSideProfile = "right",
  onCancel,
  onCaptured,
  onGhostScaleChange,
  onSideProfileChange,
  sex,
  view,
}: BodyPhotoCaptureProps) {
  const { canRequestPermission, hasPermission, requestPermission } = useCameraPermission();
  const [captureMode, setCaptureMode] = useState<"camera" | "library">(initialCaptureMode);
  const [cameraPosition, setCameraPosition] = useState<CameraPosition>("front");
  const [captured, setCaptured] = useState<BodyPhotoCapturedAsset | null>(null);
  const [countdown, setCountdown] = useState<number | null>(null);
  const [ghostScale, setGhostScale] = useState(initialGhostScale);
  const [sideProfile, setSideProfile] = useState(initialSideProfile);
  const [previewReady, setPreviewReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [liveStatus, setLiveStatus] = useState<LiveStatus>("loading");
  const [liveWarnings, setLiveWarnings] = useState<LiveWarning[]>([]);
  const nativeVision = useMemo(() => getNativeBodyVision(), []);
  const visionReady = nativeVision !== null && nativeVision.modelStatus === "ready";
  const device = useCameraDevice(cameraPosition);
  const photoOutput = usePhotoOutput({
    containerFormat: "jpeg",
    quality: 0.92,
    qualityPrioritization: "quality",
    targetResolution: { height: 1920, width: 1280 },
  });

  const onNativeVisionResult = useCallback((result: NativeBodyVisionResult) => {
    try {
      const { validation } = validateNativeBodyVisionResult(result, {
        ghostScale,
        sideProfile,
        view,
      });
      setLiveWarnings(liveWarningsFromValidation(validation));
      setLiveStatus("available");
    } catch {
      setLiveStatus("unavailable");
      setLiveWarnings([]);
    }
  }, [ghostScale, sideProfile, view]);

  const onFrame = useCallback((frame: Parameters<NonNullable<Parameters<typeof useFrameOutput>[0]["onFrame"]>>[0]) => {
    "worklet";
    try {
      if (nativeVision !== null && nativeVision.modelStatus === "ready") {
        const result = nativeVision.process(frame);
        scheduleOnRN(onNativeVisionResult, result);
      }
    } finally {
      frame.dispose();
    }
  }, [nativeVision, onNativeVisionResult]);

  const frameOutput = useFrameOutput({
    dropFramesWhileBusy: true,
    enablePhysicalBufferRotation: false,
    enablePreviewSizedOutputBuffers: true,
    onFrame,
    onFrameDropped: () => {
      "worklet";
      nativeVision?.recordDroppedFrame();
    },
    pixelFormat: "yuv",
    targetResolution: { height: 480, width: 320 },
  });
  const outputs = useMemo(
    () => visionReady ? [photoOutput, frameOutput] : [photoOutput],
    [frameOutput, photoOutput, visionReady],
  );

  useEffect(() => {
    setPreviewReady(false);
    setLiveStatus(visionReady ? "loading" : "unavailable");
    setLiveWarnings([]);
  }, [cameraPosition, captureMode, view, visionReady]);

  useEffect(() => {
    if (countdown === null) return undefined;
    const timer = setTimeout(() => {
      setCountdown((current) => advanceBodyPhotoCountdown(current));
    }, 1000);
    return () => clearTimeout(timer);
  }, [countdown]);

  const capturePhoto = useCallback(async () => {
    if (!previewReady || busy || captured !== null) return;
    setBusy(true);
    setCameraError(null);
    try {
      const photoFile = await photoOutput.capturePhotoToFile(
        { enableShutterSound: true, flashMode: "off" },
        {},
      );
      const uri = filePathToUri(photoFile.filePath);
      const { height, width } = await readImageDimensions(uri);
      setCaptured({
        height,
        mimeType: "image/jpeg",
        source: "camera",
        uri,
        width,
      });
      setPreviewReady(false);
    } catch (error) {
      setCameraError(bodyPhotoCaptureErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }, [busy, captured, photoOutput, previewReady]);

  useEffect(() => {
    if (countdown !== 0) return;
    setCountdown(null);
    void capturePhoto();
  }, [capturePhoto, countdown]);

  function updateGhostScale(nextScale: number) {
    const next = stepGhostScale(nextScale, 0);
    setGhostScale(next);
    onGhostScaleChange?.(next);
  }

  function updateSideProfile(next: BodyPhotoSide) {
    setSideProfile(next);
    onSideProfileChange?.(next);
  }

  function changeGhostScale(delta: number) {
    updateGhostScale(stepGhostScale(ghostScale, delta));
  }

  async function requestCameraAccess() {
    setCameraError(null);
    const granted = await requestPermission();
    if (!granted) setCameraError("دسترسی به دوربین داده نشد. از انتخاب عکس استفاده کن.");
  }

  async function chooseFromLibrary() {
    if (busy || captured !== null) return;
    setBusy(true);
    setConfirmError(null);
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        allowsEditing: false,
        base64: false,
        exif: false,
        mediaTypes: ["images"],
      });
      if (result.canceled) return;
      const asset = result.assets[0];
      if (asset === undefined) throw new Error("No photo selected");
      const mimeType = bodyPhotoMimeTypeForAsset(asset.mimeType, asset.uri);
      if (mimeType === null) throw new Error("Unsupported photo format");
      if (asset.width <= 0 || asset.height <= 0) throw new Error("Invalid photo dimensions");
      setCaptured({
        height: asset.height,
        mimeType,
        source: "library",
        uri: asset.uri,
        width: asset.width,
      });
    } catch (error) {
      setConfirmError(bodyPhotoCaptureErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  function discardCaptured() {
    if (captured?.source === "camera") {
      try {
        const file = new File(captured.uri);
        if (file.exists) file.delete();
      } catch {
        // The temporary camera file is best-effort cleanup only.
      }
    }
    setCaptured(null);
    setConfirmError(null);
    setCameraError(null);
    setPreviewReady(false);
  }

  async function confirmCaptured() {
    if (captured === null || busy) return;
    setBusy(true);
    setConfirmError(null);
    try {
      await onCaptured(captured);
    } catch {
      setConfirmError("ثبت این تصویر انجام نشد. دوباره تلاش کن.");
    } finally {
      setBusy(false);
    }
  }

  function closeCapture() {
    setCountdown(null);
    discardCaptured();
    onCancel();
  }

  useAndroidBackHandler(
    "wizard",
    () => {
      if (countdown !== null) {
        setCountdown(null);
        return true;
      }
      if (captured !== null) {
        discardCaptured();
        return true;
      }
      onCancel();
      return true;
    },
    true,
  );

  const cameraContent = !hasPermission ? (
    <View style={styles.cameraMessage}>
      <Text style={styles.cameraMessageTitle}>دسترسی دوربین لازم است</Text>
      <Text style={styles.cameraMessageBody}>
        برای راهنمای زنده می‌توانی دوربین را فعال کنی؛ انتخاب عکس همیشه در دسترس است.
      </Text>
      {canRequestPermission ? (
        <Button label="فعال‌کردن دوربین" onPress={() => void requestCameraAccess()} />
      ) : (
        <Notice message="دسترسی دوربین رد شده است. از تنظیمات دستگاه آن را فعال کن یا عکس انتخاب کن." variant="warning" />
      )}
    </View>
  ) : device === undefined ? (
    <View style={styles.cameraMessage}>
      <Text style={styles.cameraMessageTitle}>دوربین پیدا نشد</Text>
      <Text style={styles.cameraMessageBody}>از انتخاب عکس استفاده کن.</Text>
    </View>
  ) : cameraError !== null ? (
    <View style={styles.cameraMessage}>
      <Notice message={cameraError} variant="danger" />
      <Button label="تلاش دوباره با دوربین" onPress={() => setCameraError(null)} variant="secondary" />
    </View>
  ) : (
    <Camera
      device={device}
      enableNativeTapToFocusGesture
      isActive={captureMode === "camera" && captured === null}
      mirrorMode="off"
      onError={(error) => setCameraError(bodyPhotoCaptureErrorMessage(error))}
      onPreviewStarted={() => setPreviewReady(true)}
      onPreviewStopped={() => setPreviewReady(false)}
      orientationSource="device"
      outputs={outputs}
      style={StyleSheet.absoluteFill}
    />
  );

  return (
    <View style={styles.container}>
      <View style={styles.heading}>
        <Text style={styles.eyebrow}>ثبت تصویر · {viewLabel(view)}</Text>
        <Text style={styles.title}>در جای درست بایست</Text>
        <Text style={styles.body}>شبح فقط راهنمای حالت و موقعیت است؛ ظاهر بدن معیار رد شدن نیست.</Text>
      </View>

      <View style={styles.sourceTabs}>
        <Button
          label="دوربین"
          onPress={() => {
            setCaptureMode("camera");
            setConfirmError(null);
          }}
          style={styles.sourceButton}
          variant={captureMode === "camera" ? "primary" : "secondary"}
        />
        <Button
          label="انتخاب عکس"
          onPress={() => {
            setCaptureMode("library");
            setConfirmError(null);
          }}
          style={styles.sourceButton}
          variant={captureMode === "library" ? "primary" : "secondary"}
        />
      </View>

      <View accessibilityLabel="مرحله ثبت عکس" style={styles.stage}>
        {captured === null ? (
          captureMode === "camera" ? cameraContent : (
            <View style={styles.cameraMessage}>
              <Text style={styles.cameraMessageTitle}>عکس آماده داری؟</Text>
              <Text style={styles.cameraMessageBody}>عکس واضح و عمودی از همین نمای بدن انتخاب کن.</Text>
              <Button label="انتخاب از گالری" loading={busy} onPress={() => void chooseFromLibrary()} />
            </View>
          )
        ) : (
          <Image
            accessibilityLabel={`پیش‌نمایش ${viewLabel(view)}`}
            resizeMode="contain"
            source={{ uri: captured.uri } as ImageSourcePropType}
            style={styles.capturedImage}
          />
        )}
        <GhostOverlayGuide ghostScale={ghostScale} sideProfile={sideProfile} sex={sex} view={view} />
        {countdown !== null && captured === null ? (
          <View accessibilityLiveRegion="polite" style={styles.countdown}>
            <Text style={styles.countdownText}>{countdown}</Text>
          </View>
        ) : null}
      </View>

      {view === "side" ? (
        <View style={styles.sideToggle}>
          <Text style={styles.controlLabel}>جهت نیمرخ</Text>
          <View style={styles.inlineButtons}>
            <Button
              disabled={captured !== null || busy}
              label="راست"
              onPress={() => updateSideProfile("right")}
              variant={sideProfile === "right" ? "primary" : "secondary"}
            />
            <Button
              disabled={captured !== null || busy}
              label="چپ"
              onPress={() => updateSideProfile("left")}
              variant={sideProfile === "left" ? "primary" : "secondary"}
            />
          </View>
        </View>
      ) : null}

      {captured === null ? (
        <>
          <View style={styles.scaleControls}>
            <Text style={styles.controlLabel}>اندازه راهنما</Text>
            <View style={styles.inlineButtons}>
              <Button
                disabled={busy || ghostScale <= GHOST_SCALE_MIN}
                label="کوچک‌تر"
                onPress={() => changeGhostScale(-GHOST_SCALE_STEP)}
                variant="secondary"
              />
              <Text style={styles.scaleValue}>{Math.round(ghostScale * 100)}٪</Text>
              <Button
                disabled={busy || ghostScale >= GHOST_SCALE_MAX}
                label="بزرگ‌تر"
                onPress={() => changeGhostScale(GHOST_SCALE_STEP)}
                variant="secondary"
              />
            </View>
          </View>
          {captureMode === "camera" && hasPermission && device !== undefined ? (
            <View style={styles.cameraActions}>
              <Button
                disabled={!previewReady || countdown !== null || busy}
                label={countdown === null ? "شروع شمارش ۵ ثانیه‌ای" : "در حال شمارش…"}
                onPress={() => setCountdown(BODY_PHOTO_COUNTDOWN_SECONDS)}
              />
              <Button
                disabled={busy || countdown !== null}
                label={cameraPosition === "front" ? "دوربین پشت" : "دوربین جلو"}
                onPress={() => {
                  setCameraPosition((current) => current === "front" ? "back" : "front");
                  setCameraError(null);
                }}
                variant="secondary"
              />
              {countdown !== null ? (
                <Button label="لغو شمارش" onPress={() => setCountdown(null)} variant="ghost" />
              ) : null}
            </View>
          ) : null}
          {visionReady && liveStatus === "available" ? (
            <Text style={styles.liveStatus}>راهنمای زنده فعال است.</Text>
          ) : visionReady ? (
            <Text style={styles.liveStatus}>راهنمای زنده در حال آماده‌سازی است.</Text>
          ) : (
            <Text style={styles.liveStatus}>راهنمای زنده روی این نسخه در دسترس نیست؛ ثبت عکس همچنان ممکن است.</Text>
          )}
          {liveWarnings.length > 0 ? (
            <Notice message={liveWarnings.map(liveWarningLabel).join(" · ")} variant="warning" />
          ) : null}
        </>
      ) : (
        <View style={styles.confirmActions}>
          <Button disabled={busy} label="گرفتن دوباره" onPress={discardCaptured} variant="secondary" />
          <Button disabled={busy} label="تأیید این عکس" loading={busy} onPress={() => void confirmCaptured()} />
        </View>
      )}

      {confirmError !== null ? <Notice message={confirmError} variant="danger" /> : null}
      <Button disabled={busy} label="بستن این مرحله" onPress={closeCapture} variant="ghost" />
    </View>
  );
}

function liveWarningsFromValidation(validation: GhostPoseValidationResult): LiveWarning[] {
  const warnings = new Set<LiveWarning>();
  if (validation.warnings.includes("person_missing") || validation.hardRejectCode === "body_not_detected") {
    warnings.add("person_missing");
  }
  if (validation.warnings.includes("multiple_people") || validation.hardRejectCode === "multiple_people_detected") {
    warnings.add("multiple_people");
  }
  if (validation.warnings.includes("body_out_of_frame") || validation.hardRejectCode === "body_out_of_frame") {
    warnings.add("body_out_of_frame");
  }
  if (validation.warnings.includes("too_close")) warnings.add("too_close");
  if (validation.warnings.includes("too_far")) warnings.add("too_far");
  if (validation.warnings.includes("wrong_view") || validation.hardRejectCode === "unexpected_body_view") {
    warnings.add("wrong_view");
  }
  return [...warnings];
}

function liveWarningLabel(warning: LiveWarning): string {
  const labels: Record<LiveWarning, string> = {
    body_out_of_frame: "تمام بدن داخل کادر نیست",
    multiple_people: "فقط یک نفر باید در کادر باشد",
    person_missing: "بدن پیدا نشد",
    too_close: "کمی دورتر بایست",
    too_far: "کمی نزدیک‌تر بایست",
    wrong_view: "نمای انتخاب‌شده را رعایت کن",
  };
  return labels[warning];
}

function viewLabel(view: BodyPhotoView): string {
  if (view === "front") return "روبه‌رو";
  if (view === "side") return "نیمرخ";
  return "پشت";
}

function readImageDimensions(uri: string): Promise<{ height: number; width: number }> {
  return new Promise((resolve, reject) => {
    Image.getSize(uri, (width, height) => resolve({ height, width }), reject);
  });
}

const styles = StyleSheet.create({
  body: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "right",
    writingDirection: "rtl",
  },
  cameraActions: {
    gap: fiticianTokens.spacing[2],
  },
  cameraMessage: {
    alignItems: "center",
    gap: fiticianTokens.spacing[3],
    justifyContent: "center",
    padding: fiticianTokens.spacing[5],
  },
  cameraMessageBody: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "center",
    writingDirection: "rtl",
  },
  cameraMessageTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.lg,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "center",
    writingDirection: "rtl",
  },
  capturedImage: {
    height: "100%",
    width: "100%",
  },
  confirmActions: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  container: {
    gap: fiticianTokens.spacing[3],
  },
  controlLabel: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  countdown: {
    alignItems: "center",
    backgroundColor: "rgba(2,6,7,0.64)",
    bottom: 0,
    justifyContent: "center",
    left: 0,
    position: "absolute",
    right: 0,
    top: 0,
  },
  countdownText: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: 92,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
  },
  eyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  heading: {
    gap: fiticianTokens.spacing[2],
  },
  inlineButtons: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  liveStatus: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "right",
    writingDirection: "rtl",
  },
  scaleControls: {
    gap: fiticianTokens.spacing[2],
  },
  scaleValue: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.body,
    minWidth: 54,
    textAlign: "center",
  },
  sideToggle: {
    gap: fiticianTokens.spacing[2],
  },
  sourceButton: {
    flex: 1,
  },
  sourceTabs: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  stage: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    height: 520,
    overflow: "hidden",
    position: "relative",
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 42,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
