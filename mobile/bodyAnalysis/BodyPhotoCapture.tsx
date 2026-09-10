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
import { AppIcon, Button, Notice, PageHeading } from "../ui/components";
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
  bodyPhotoPrivacyProcessingErrorMessage,
  filePathToUri,
  type BodyPhotoCapturedAsset,
} from "./cameraCapture";
import { encodeBodyPhotoWithPrivacyCrop } from "./bodyPhotoEncoder";
import { bodyPhotoCopy } from "./bodyAnalysisCopy";

export interface BodyPhotoCaptureProps {
  readonly completedViews?: readonly BodyPhotoView[];
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
  completedViews = [],
  initialCaptureMode = "library",
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
    let rawUri: string | null = null;
    let encodedUri: string | null = null;
    try {
      const photoFile = await photoOutput.capturePhotoToFile(
        { enableShutterSound: true, flashMode: "off" },
        {},
      );
      rawUri = filePathToUri(photoFile.filePath);
      const { height, width } = await readImageDimensions(rawUri);
      const encoded = await encodeBodyPhotoWithPrivacyCrop({
        height,
        source: "camera",
        uri: rawUri,
        width,
      }, { ghostScale, sideProfile, view });
      encodedUri = encoded.uri;
      setCaptured(encoded);
      setPreviewReady(false);
    } catch (error) {
      setCameraError(rawUri === null
        ? bodyPhotoCaptureErrorMessage(error)
        : bodyPhotoPrivacyProcessingErrorMessage());
    } finally {
      if (rawUri !== null && rawUri !== encodedUri) deleteLocalFile(rawUri);
      setBusy(false);
    }
  }, [busy, captured, ghostScale, photoOutput, previewReady, sideProfile, view]);

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
      const encoded = await encodeBodyPhotoWithPrivacyCrop({
        height: asset.height,
        source: "library",
        uri: asset.uri,
        width: asset.width,
      }, { ghostScale, sideProfile, view });
      setCaptured(encoded);
    } catch (error) {
      setConfirmError(error instanceof Error && error.message === "No photo selected"
        ? bodyPhotoCaptureErrorMessage(error)
        : bodyPhotoPrivacyProcessingErrorMessage());
    } finally {
      setBusy(false);
    }
  }

  function discardCaptured() {
    if (captured !== null) deleteLocalFile(captured.uri);
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
      <PageHeading
        compact
        eyebrow={`${bodyPhotoCopy.eyebrow} · ${viewLabel(view)}`}
        supportingText="راهنمای Ghost فقط برای حالت و موقعیت است؛ ظاهر بدن معیار رد شدن نیست."
        title={bodyPhotoCopy.title}
      />

      <PhotoClothingGuide />
      <CaptureStepIndicator completedViews={completedViews} currentView={view} />

      <View style={styles.captureIntro}>
        <Text style={styles.captureBadge}>SCAN VIEW: {view.toUpperCase()}</Text>
        <Text style={styles.captureTitle}>{replaceView(bodyPhotoCopy.captureTitle, viewLabel(view))}</Text>
        <Text style={styles.body}>{bodyPhotoCopy.pose[view]}</Text>
        <Text style={styles.captureHint}>{bodyPhotoCopy.cameraGuidance}</Text>
      </View>

      {view === "side" ? (
        <View style={styles.sideToggle}>
          <Text style={styles.controlLabel}>جهت عکاسی نیمرخ</Text>
          <View style={styles.inlineButtons}>
            <Button
              disabled={captured !== null || busy}
              label={bodyPhotoCopy.sideProfile.right}
              onPress={() => updateSideProfile("right")}
              variant={sideProfile === "right" ? "primary" : "secondary"}
            />
            <Button
              disabled={captured !== null || busy}
              label={bodyPhotoCopy.sideProfile.left}
              onPress={() => updateSideProfile("left")}
              variant={sideProfile === "left" ? "primary" : "secondary"}
            />
          </View>
        </View>
      ) : null}

      {captureMode === "library" ? <HeadlessPhotoGuide /> : null}
      <View accessibilityLabel="مرحله ثبت عکس" style={styles.stage}>
        {captured === null ? (
          captureMode === "camera" ? cameraContent : (
            <View style={styles.libraryCaptureDeck}>
              <View style={styles.libraryGuideBadge}>
                <AppIcon color={fiticianTokens.colors.aqua} name="target" size={20} />
              </View>
              <Text style={styles.libraryGuideTitle}>{bodyPhotoCopy.headlessInstruction}</Text>
              <Text style={styles.cameraMessageBody}>{replaceView(bodyPhotoCopy.uploadExistingPhoto, viewLabel(view))}</Text>
              <View style={styles.sourceActions}>
                <Button
                  disabled={busy}
                  label={bodyPhotoCopy.useCamera}
                  onPress={() => {
                    setCaptureMode("camera");
                    setConfirmError(null);
                  }}
                  variant="secondary"
                />
                <Button
                  label={replaceView(bodyPhotoCopy.uploadExistingPhoto, viewLabel(view))}
                  loading={busy}
                  onPress={() => void chooseFromLibrary()}
                />
              </View>
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
          <Button
            disabled={busy}
            label={replaceView(bodyPhotoCopy.retake, viewLabel(view))}
            onPress={discardCaptured}
            variant="secondary"
          />
          <Button
            disabled={busy}
            label={replaceView(bodyPhotoCopy.confirmUpload, viewLabel(view))}
            loading={busy}
            onPress={() => void confirmCaptured()}
          />
        </View>
      )}

      {confirmError !== null ? <Notice message={confirmError} variant="danger" /> : null}
      <Button disabled={busy} label="بستن این مرحله" onPress={closeCapture} variant="ghost" />
    </View>
  );
}

export function PhotoClothingGuide() {
  return (
    <View accessibilityLabel="لباس و پوشش مناسب" style={styles.clothingGuide}>
      <View style={styles.clothingHeader}>
        <Text style={styles.clothingTitle}>{bodyPhotoCopy.clothingTitle}</Text>
        <View style={styles.clothingIcon}>
          <AppIcon color={fiticianTokens.colors.amber} name="shield" size={18} />
        </View>
      </View>
      <Text style={styles.captureHint}>{bodyPhotoCopy.clothingBody}</Text>
      <Text style={styles.captureHint}>{bodyPhotoCopy.coverage}</Text>
    </View>
  );
}

function HeadlessPhotoGuide() {
  const retained = ["shouldersArms", "waistHips", "legsKnees", "anklesFeet"] as const;
  return (
    <View accessibilityLabel={bodyPhotoCopy.headlessGuideLabel} style={styles.headlessGuide}>
      <View style={styles.headlessHeader}>
        <View style={styles.headlessBadge}>
          <AppIcon color={fiticianTokens.colors.aqua} name="shield" size={18} />
        </View>
        <View style={styles.headlessCopy}>
          <Text style={styles.headlessTitle}>{bodyPhotoCopy.headlessInstruction}</Text>
          <Text style={styles.captureHint}>{bodyPhotoCopy.headlessGuideIntro}</Text>
        </View>
      </View>
      <View style={styles.retainedList}>
        {retained.map((item) => (
          <View key={item} style={styles.retainedItem}>
            <Text style={styles.retainedCheck}>✓</Text>
            <Text style={styles.captureHint}>{bodyPhotoCopy.retained[item]}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

function CaptureStepIndicator({
  completedViews,
  currentView,
}: {
  readonly completedViews: readonly BodyPhotoView[];
  readonly currentView: BodyPhotoView;
}) {
  return (
    <View accessible accessibilityLabel="مراحل ثبت عکس" style={styles.stepList}>
      {(["front", "side", "back"] as const).map((step, index) => {
        const completed = completedViews.includes(step);
        const current = currentView === step;
        const stateLabel = completed ? "، انجام‌شده" : current ? "، مرحله فعلی" : "";
        return (
          <View
            accessible
            accessibilityLabel={`نمای ${viewLabel(step)}${stateLabel}`}
            accessibilityRole="text"
            accessibilityState={{ selected: current }}
            key={step}
            style={[styles.stepItem, current && styles.stepItemActive, completed && styles.stepItemCompleted]}
          >
            <Text style={styles.stepIndex}>0{index + 1}</Text>
            <Text style={[styles.stepLabel, current && styles.stepLabelActive, completed && styles.stepLabelCompleted]}>
              {viewLabel(step)}
            </Text>
            {completed ? <Text style={styles.stepCheck}>✓</Text> : null}
          </View>
        );
      })}
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

function replaceView(template: string, view: string): string {
  return template.replace("{{view}}", view);
}

function readImageDimensions(uri: string): Promise<{ height: number; width: number }> {
  return new Promise((resolve, reject) => {
    Image.getSize(uri, (width, height) => resolve({ height, width }), reject);
  });
}

function deleteLocalFile(uri: string): void {
  try {
    const file = new File(uri);
    if (file.exists) file.delete();
  } catch {
    // Temporary crop cleanup is best effort only.
  }
}

const styles = StyleSheet.create({
  body: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "auto",
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
  captureBadge: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    letterSpacing: 1,
    textAlign: "right",
  },
  captureHint: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  captureIntro: {
    gap: fiticianTokens.spacing[1],
  },
  captureTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 30,
    textAlign: "auto",
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
  clothingGuide: {
    backgroundColor: fiticianTokens.colors.warningSurface,
    borderColor: "rgba(242,184,91,0.26)",
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[2],
    padding: fiticianTokens.spacing[3],
  },
  clothingHeader: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  clothingIcon: {
    alignItems: "center",
    backgroundColor: "rgba(242,184,91,0.12)",
    borderColor: "rgba(242,184,91,0.38)",
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    height: 32,
    justifyContent: "center",
    width: 32,
  },
  clothingTitle: {
    color: fiticianTokens.colors.amber,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  headlessBadge: {
    alignItems: "center",
    backgroundColor: "rgba(80,223,206,0.12)",
    borderColor: "rgba(80,223,206,0.32)",
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    height: 34,
    justifyContent: "center",
    width: 34,
  },
  headlessCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  headlessGuide: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: "rgba(80,223,206,0.24)",
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[3],
  },
  headlessHeader: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
  headlessTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 24,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  controlLabel: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
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
    textAlign: "auto",
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
  libraryCaptureDeck: {
    alignItems: "center",
    gap: fiticianTokens.spacing[3],
    justifyContent: "flex-end",
    padding: fiticianTokens.spacing[4],
    paddingBottom: fiticianTokens.spacing[5],
    paddingTop: fiticianTokens.spacing[5],
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    zIndex: 3,
  },
  libraryGuideBadge: {
    alignItems: "center",
    backgroundColor: "rgba(2,6,7,0.76)",
    borderColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    height: 44,
    justifyContent: "center",
    width: 44,
  },
  libraryGuideTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "center",
    writingDirection: "rtl",
  },
  retainedCheck: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
  },
  retainedItem: {
    alignItems: "center",
    flex: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[1],
  },
  retainedList: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  sourceActions: {
    alignSelf: "stretch",
    gap: fiticianTokens.spacing[2],
  },
  liveStatus: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "auto",
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
    writingDirection: "ltr",
  },
  sideToggle: {
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
  stepCheck: {
    color: fiticianTokens.colors.success,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
  },
  stepIndex: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: 11,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
  },
  stepItem: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flex: 1,
    gap: fiticianTokens.spacing[1],
    justifyContent: "center",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[1],
    paddingVertical: fiticianTokens.spacing[2],
  },
  stepItemActive: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.aqua,
  },
  stepItemCompleted: {
    backgroundColor: fiticianTokens.colors.successSurface,
    borderColor: fiticianTokens.colors.success,
  },
  stepLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "center",
    writingDirection: "rtl",
  },
  stepLabelActive: {
    color: fiticianTokens.colors.aqua,
  },
  stepLabelCompleted: {
    color: fiticianTokens.colors.success,
  },
  stepList: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 42,
    textAlign: "auto",
    writingDirection: "rtl",
  },
});
