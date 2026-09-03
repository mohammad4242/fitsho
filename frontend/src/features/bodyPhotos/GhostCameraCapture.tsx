import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { Sex } from "../profile/types";
import { GhostOverlayGuide } from "./GhostOverlayGuide";
import { GhostScaleControls } from "./GhostScaleControls";
import {
  GHOST_EDITOR_DEFAULT_TRANSFORM,
  privacyCropSourceYForView,
} from "./ghostPhotoEditor";
import {
  createMediaPipeLivePoseGuide,
  type LivePoseGuidance,
  type LivePoseGuideFactory,
} from "./livePoseGuide";
import type { BodyPhotoSide, BodyPhotoView, GhostTransform } from "./types";

export type CameraFallbackReason =
  | "unsupported"
  | "insecure_context"
  | "permission_denied"
  | "camera_error"
  | "visibility_loss";

type CameraFacingMode = "user" | "environment";

type GhostCameraCaptureProps = {
  sex?: Sex | null;
  sideProfile?: BodyPhotoSide;
  view: BodyPhotoView;
  onFileCaptured: (file: File) => void | Promise<void>;
  onFallback: (reason: CameraFallbackReason) => void;
  onClose: () => void;
  livePoseGuideFactory?: LivePoseGuideFactory;
};

export { GHOST_PRIVACY_CUT_RATIO } from "./ghostPhotoEditor";

const cameraConstraints = {
  audio: false,
  video: {
    facingMode: { ideal: "user" },
    width: { ideal: 1280 },
    height: { ideal: 1920 },
  },
} as const;

export function GhostCameraCapture({
  sex,
  sideProfile,
  view,
  onFileCaptured,
  onFallback,
  onClose,
  livePoseGuideFactory = defaultLivePoseGuideFactory,
}: GhostCameraCaptureProps) {
  const { t } = useTranslation();
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const mountedRef = useRef(true);
  const streamRef = useRef<MediaStream | null>(null);
  const [facingMode, setFacingMode] = useState<CameraFacingMode>("user");
  const [cameraGeneration, setCameraGeneration] = useState(0);
  const [canToggleFacingMode, setCanToggleFacingMode] = useState(true);
  const [streamReady, setStreamReady] = useState(false);
  const [countdown, setCountdown] = useState<number | null>(null);
  const [capturedFile, setCapturedFile] = useState<File | null>(null);
  const [capturedPreviewUrl, setCapturedPreviewUrl] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [ghostTransform, setGhostTransform] = useState<GhostTransform>(GHOST_EDITOR_DEFAULT_TRANSFORM);
  const [liveStatus, setLiveStatus] = useState<"loading" | "available" | "unavailable" | "disabled">("loading");
  const [guidance, setGuidance] = useState<LivePoseGuidance>({ status: "available", warnings: [] });

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const captureFrame = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (video === null || canvas === null || !streamReady || video.videoWidth <= 0 || video.videoHeight <= 0) {
      onFallback("camera_error");
      return;
    }
    const displaySize = getCameraDisplaySize(stageRef.current, video.videoWidth, video.videoHeight);
    const sourceY = Math.round(privacyCropSourceYForView(
      view,
      ghostTransform,
      displaySize,
      { width: video.videoWidth, height: video.videoHeight },
    ));
    const outputHeight = video.videoHeight - sourceY;
    canvas.width = video.videoWidth;
    canvas.height = outputHeight;
    const context = canvas.getContext("2d");
    if (context === null) {
      onFallback("camera_error");
      return;
    }
    context.save();
    if (facingMode === "user") {
      context.translate(canvas.width, 0);
      context.scale(-1, 1);
    }
    context.drawImage(
      video,
      0,
      sourceY,
      video.videoWidth,
      outputHeight,
      0,
      0,
      canvas.width,
      canvas.height,
    );
    context.restore();
    canvas.toBlob((blob) => {
      if (blob === null || blob.size === 0) {
        onFallback("camera_error");
        return;
      }
      if (!mountedRef.current) return;
      const file = new File([blob], `body-camera-${view}-${Date.now()}.jpg`, {
        type: "image/jpeg",
        lastModified: Date.now(),
      });
      setCapturedFile(file);
      setCapturedPreviewUrl(URL.createObjectURL(file));
      setStreamReady(false);
      stopCurrentStream();
    }, "image/jpeg", 0.92);
  }, [facingMode, ghostTransform, onFallback, streamReady, view]);

  useEffect(() => {
    const capability = detectCameraCapability();
    setCanToggleFacingMode(capability.toggleFacingMode);
    if (capability.reason !== null) {
      onFallback(capability.reason);
      return;
    }

    let active = true;
    setStreamReady(false);
    const video = videoRef.current;
    const mediaDevices = navigator.mediaDevices;
    if (video === null || mediaDevices === undefined) {
      onFallback("unsupported");
      return;
    }
    const handleMetadata = () => {
      if (active) setStreamReady(true);
    };
    video.addEventListener("loadedmetadata", handleMetadata);
    void mediaDevices.getUserMedia({
      ...cameraConstraints,
      video: {
        ...cameraConstraints.video,
        facingMode: { ideal: facingMode },
      },
    })
      .then((stream) => {
        if (!active) {
          stopStream(stream);
          return;
        }
        streamRef.current = stream;
        video.srcObject = stream;
        void video.play().catch(() => undefined);
        if (video.readyState >= 2) setStreamReady(true);
      })
      .catch((error: unknown) => {
        if (!active) return;
        onFallback(cameraErrorReason(error));
      });

    return () => {
      active = false;
      video.removeEventListener("loadedmetadata", handleMetadata);
      stopCurrentStream();
    };
  }, [cameraGeneration, facingMode, onFallback]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        stopCurrentStream();
        onFallback("visibility_loss");
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, [onFallback]);

  useEffect(() => {
    if (countdown === null) return;
    if (countdown === 0) {
      setCountdown(null);
      captureFrame();
      return;
    }
    const timer = window.setTimeout(() => setCountdown(countdown - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [captureFrame, countdown]);

  useEffect(() => {
    return () => {
      if (capturedPreviewUrl !== null) URL.revokeObjectURL(capturedPreviewUrl);
    };
  }, [capturedPreviewUrl]);

  useEffect(() => {
    if (!streamReady) return;
    if (isSlowDevice()) {
      setLiveStatus("disabled");
      return;
    }

    let active = true;
    let timer: number | null = null;
    let liveGuide: Awaited<ReturnType<LivePoseGuideFactory>> | null = null;
    setLiveStatus("loading");
    void livePoseGuideFactory(view)
      .then((createdGuide) => {
        if (!active) {
          createdGuide.close();
          return;
        }
        liveGuide = createdGuide;
        setLiveStatus("available");
        const check = () => {
          if (!active || liveGuide === null) return;
          const video = videoRef.current;
          if (video !== null && video.readyState >= 2) {
            const nextGuidance = liveGuide.check(video, performance.now());
            setGuidance(nextGuidance);
            setLiveStatus(nextGuidance.status === "available" ? "available" : "unavailable");
          }
          timer = window.setTimeout(check, 200);
        };
        check();
      })
      .catch(() => {
        if (active) setLiveStatus("unavailable");
      });

    return () => {
      active = false;
      if (timer !== null) window.clearTimeout(timer);
      liveGuide?.close();
    };
  }, [livePoseGuideFactory, streamReady, view]);

  function startCountdown() {
    if (!streamReady || capturedFile !== null || countdown !== null || confirming) return;
    setCountdown(5);
  }

  function retake() {
    setCapturedFile(null);
    setCapturedPreviewUrl(null);
    setStreamReady(false);
    setCameraGeneration((current) => current + 1);
    stopCurrentStream();
  }

  async function confirmCapture() {
    if (capturedFile === null || confirming) return;
    setConfirming(true);
    try {
      await onFileCaptured(capturedFile);
    } catch {
      onFallback("camera_error");
    } finally {
      setConfirming(false);
    }
  }

  function toggleFacingMode() {
    if (!canToggleFacingMode || capturedFile !== null || confirming) return;
    setCountdown(null);
    setStreamReady(false);
    setFacingMode((current) => current === "user" ? "environment" : "user");
  }

  function closeCamera() {
    setCountdown(null);
    stopCurrentStream();
    onClose();
  }

  function stopCurrentStream() {
    const video = videoRef.current;
    if (video !== null) {
      video.pause();
      video.srcObject = null;
    }
    const stream = streamRef.current;
    if (stream !== null) {
      stopStream(stream);
      streamRef.current = null;
    }
  }

  const warningText = guidance.warnings.map((warning) => (
    <li key={warning}>{t(`bodyPhotos.camera.warnings.${warning}`)}</li>
  ));

  return (
    <section className="ghost-camera" aria-labelledby="ghost-camera-title">
      <div className="ghost-camera__heading">
        <h3 id="ghost-camera-title">{t("bodyPhotos.camera.title", { view: t(`bodyPhotos.views.${view}`) })}</h3>
        <p>{t("bodyPhotos.camera.body")}</p>
      </div>
      <div ref={stageRef} className="ghost-camera__stage">
        {capturedPreviewUrl === null ? (
          <video
            ref={videoRef}
            className={facingMode === "user" ? "ghost-camera__video ghost-camera__video--mirrored" : "ghost-camera__video"}
            autoPlay
            muted
            playsInline
            aria-label={t("bodyPhotos.camera.liveLabel")}
          />
        ) : (
          <img
            className="ghost-camera__captured"
            src={capturedPreviewUrl}
            alt={t("bodyPhotos.camera.capturedAlt", { view: t(`bodyPhotos.views.${view}`) })}
          />
        )}
        <GhostOverlayGuide sex={sex} transform={ghostTransform} sideProfile={sideProfile} view={view} />
      </div>
      <canvas ref={canvasRef} className="ghost-camera__canvas" aria-hidden="true" />
      {capturedFile === null ? (
        <>
          <GhostScaleControls
            disabled={confirming}
            onScaleChange={(scale) => setGhostTransform((current) => ({ ...current, scale }))}
            scale={ghostTransform.scale}
          />
          <p className="ghost-camera__privacy-note">{t("bodyPhotos.camera.privacyBody")}</p>
          {liveStatus === "unavailable" && <p className="body-photo-muted">{t("bodyPhotos.camera.liveUnavailable")}</p>}
          {liveStatus === "disabled" && <p className="body-photo-muted">{t("bodyPhotos.camera.liveDisabled")}</p>}
          {warningText.length > 0 && (
            <ul className="ghost-camera__warnings" aria-label={t("bodyPhotos.camera.advisoryLabel")}>
              {warningText}
            </ul>
          )}
          {countdown !== null ? (
            <div className="ghost-camera__countdown" role="status">
              {t("bodyPhotos.camera.countdown", { seconds: countdown })}
              <button className="body-photo-link-button" type="button" onClick={() => setCountdown(null)}>
                {t("bodyPhotos.camera.cancelTimer")}
              </button>
            </div>
          ) : (
            <button className="primary-button" type="button" onClick={startCountdown} disabled={!streamReady || confirming}>
              {t("bodyPhotos.camera.startTimer")}
            </button>
          )}
          {canToggleFacingMode && (
            <button className="secondary-button" type="button" onClick={toggleFacingMode} disabled={!streamReady || confirming}>
              {facingMode === "user" ? t("bodyPhotos.camera.environmentCamera") : t("bodyPhotos.camera.frontCamera")}
            </button>
          )}
        </>
      ) : (
        <div className="ghost-camera__actions">
          <button className="secondary-button" type="button" onClick={retake} disabled={confirming}>
            {t("bodyPhotos.camera.retake")}
          </button>
          <button className="primary-button" type="button" onClick={() => void confirmCapture()} disabled={confirming}>
            {confirming ? t("bodyPhotos.camera.confirming") : t("bodyPhotos.camera.confirm")}
          </button>
        </div>
      )}
      <button className="body-photo-link-button ghost-camera__close" type="button" onClick={closeCamera} disabled={confirming}>
        {t("bodyPhotos.camera.close")}
      </button>
    </section>
  );
}

function detectCameraCapability(): {
  reason: CameraFallbackReason | null;
  toggleFacingMode: boolean;
} {
  if (typeof window === "undefined" || window.isSecureContext !== true) {
    return { reason: "insecure_context", toggleFacingMode: false };
  }
  const mediaDevices = typeof navigator === "undefined" ? undefined : navigator.mediaDevices;
  if (mediaDevices?.getUserMedia === undefined) {
    return { reason: "unsupported", toggleFacingMode: false };
  }
  try {
    const supported = mediaDevices.getSupportedConstraints?.();
    return {
      reason: null,
      toggleFacingMode: supported?.facingMode !== false,
    };
  } catch {
    return { reason: null, toggleFacingMode: false };
  }
}

function cameraErrorReason(error: unknown): CameraFallbackReason {
  if (error instanceof DOMException && ["NotAllowedError", "SecurityError"].includes(error.name)) {
    return "permission_denied";
  }
  if (typeof error === "object" && error !== null && "name" in error
    && ["NotAllowedError", "SecurityError"].includes(String(error.name))) {
    return "permission_denied";
  }
  return "camera_error";
}

function stopStream(stream: MediaStream) {
  stream.getTracks().forEach((track) => track.stop());
}

function isSlowDevice(): boolean {
  return typeof navigator.hardwareConcurrency === "number" && navigator.hardwareConcurrency <= 2;
}

const defaultLivePoseGuideFactory: LivePoseGuideFactory = (view) => createMediaPipeLivePoseGuide(view);

function getCameraDisplaySize(
  stage: HTMLDivElement | null,
  fallbackWidth: number,
  fallbackHeight: number,
): { width: number; height: number } {
  const rect = stage?.getBoundingClientRect();
  return {
    width: rect !== undefined && rect.width > 0 ? rect.width : fallbackWidth,
    height: rect !== undefined && rect.height > 0 ? rect.height : fallbackHeight,
  };
}
