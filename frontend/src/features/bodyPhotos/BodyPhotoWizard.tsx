import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "../../shared/apiClient";
import { useOptionalProfile } from "../profile/ProfileContext";

import {
  createBodyPhotoSession,
  getBodyPhotoSession,
  startBodyPhotoAnalysis,
  submitBodyPhotoSession,
  uploadBodyPhoto,
} from "./api";
import { GhostCameraCapture, type CameraFallbackReason } from "./GhostCameraCapture";
import { BodyAnalysisRequirementsStep } from "./BodyAnalysisRequirementsStep";
import { GhostPhotoEditor } from "./GhostPhotoEditor";
import {
  browserBodyPhotoProcessor,
  BodyPhotoProcessingError,
  type BodyPhotoProcessor,
  type ProcessedBodyPhoto,
} from "./processor";
import type { BodyPhotoPurpose, BodyPhotoSession, BodyPhotoSide, BodyPhotoView } from "./types";
import { AppIcon } from "../../shared/AppIcon";
import { ghostOverlayAssets, resolveGhostOverlayVariant } from "./ghostOverlayAssets";
import "./bodyPhotos.css";

const views: BodyPhotoView[] = ["front", "side", "back"];

type WizardState = "capture" | "confirm" | "complete" | "skipped";
type CaptureMode = "upload" | "camera";

type SelectedPhotoPreview = {
  view: BodyPhotoView;
  url: string;
};

export function BodyPhotoWizard({
  processor = browserBodyPhotoProcessor,
  purpose = "initial_plan",
}: {
  processor?: BodyPhotoProcessor;
  purpose?: BodyPhotoPurpose;
}) {
  const { t } = useTranslation();
  const profileContext = useOptionalProfile();
  const profileSex = profileContext?.profile?.sex ?? null;
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const editSessionId = searchParams.get("sessionId");
  const editView = views.find((item) => item === searchParams.get("view")) ?? null;
  const loadingExistingSession = editSessionId !== null;
  const editingExistingPhoto = editSessionId !== null && editView !== null;
  const [currentIndex, setCurrentIndex] = useState(() => editView === null ? 0 : views.indexOf(editView));
  const [processed, setProcessed] = useState<Partial<Record<BodyPhotoView, ProcessedBodyPhoto>>>({});
  const [session, setSession] = useState<BodyPhotoSession | null>(null);
  const [operationalConsent, setOperationalConsent] = useState(false);
  const [modelTrainingConsent, setModelTrainingConsent] = useState(false);
  const [state, setState] = useState<WizardState>("capture");
  const [requirementsConfirmed, setRequirementsConfirmed] = useState(false);
  const [captureMode, setCaptureMode] = useState<CaptureMode>("upload");
  const [sideProfile, setSideProfile] = useState<BodyPhotoSide>("right");
  const [editorFile, setEditorFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [termsOpen, setTermsOpen] = useState(false);
  const [selectedPreview, setSelectedPreview] = useState<SelectedPhotoPreview | null>(null);
  const processedRef = useRef(processed);
  const selectedPreviewRef = useRef<SelectedPhotoPreview | null>(null);
  const mountedRef = useRef(false);
  const selectionTokenRef = useRef(0);
  const [sessionLoading, setSessionLoading] = useState(loadingExistingSession);

  const view = views[currentIndex];
  const current = processed[view] ?? null;
  const overlayVariant = resolveGhostOverlayVariant(profileSex);
  const ghostSilhouetteUrl = ghostOverlayAssets[overlayVariant][view];
  const complete = views.every((item) => (
    processed[item] !== undefined || session?.photos.some((photo) => photo.view === item) === true
  ));

  useEffect(() => {
    processedRef.current = processed;
  }, [processed]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      selectionTokenRef.current += 1;
      Object.values(processedRef.current).forEach(disposeProcessedPhoto);
      disposeSelectedPreview(selectedPreviewRef.current);
      processedRef.current = {};
      selectedPreviewRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (editSessionId === null) return;
    void getBodyPhotoSession(editSessionId)
      .then((loaded) => {
        if (!mountedRef.current) return;
        setSession(loaded);
        setOperationalConsent(loaded.operational_processing_consent?.granted ?? false);
        setModelTrainingConsent(loaded.model_training_consent?.granted ?? false);
        if (editView === null) {
          const missingIndex = views.findIndex((item) => (
            !loaded.photos.some((photo) => photo.view === item)
          ));
          if (missingIndex === -1) {
            setState("confirm");
          } else {
            setCurrentIndex(missingIndex);
          }
        }
      })
      .catch(() => {
        if (mountedRef.current) setError(t("bodyPhotos.errors.load"));
      })
      .finally(() => {
        if (mountedRef.current) setSessionLoading(false);
      });
  }, [editSessionId, editView, t]);

  const instructions = useMemo(() => ({
    front: t("bodyPhotos.pose.front"),
    side: t("bodyPhotos.pose.side"),
    back: t("bodyPhotos.pose.back"),
  }), [t]);

  async function processFile(file: File, context?: { ghostScale?: number; sideProfile?: BodyPhotoSide }) {
    if (busy) return;
    const selectedView = view;
    const selectionToken = ++selectionTokenRef.current;
    replaceSelectedPreview(file, selectedView);
    setBusy(true);
    setError(null);
    try {
      const options = (context?.ghostScale !== undefined || context?.sideProfile !== undefined)
        ? {
            ...(context.ghostScale !== undefined ? { ghostScale: context.ghostScale } : {}),
            ...(context.sideProfile !== undefined ? { sideProfile: context.sideProfile } : {}),
          }
        : undefined;
      const next = options !== undefined
        ? await processor.process(file, selectedView, options)
        : await processor.process(file, selectedView);
      if (!mountedRef.current || selectionToken !== selectionTokenRef.current) {
        disposeProcessedPhoto(next);
        return;
      }
      setProcessed((currentProcessed) => {
        const previous = currentProcessed[selectedView];
        disposeProcessedPhoto(previous);
        const updated = { ...currentProcessed, [selectedView]: next };
        processedRef.current = updated;
        return updated;
      });
    } catch (processingError) {
      console.error("[BodyPhotoWizard] Failed to process body photo for view:", selectedView, processingError);
      if (mountedRef.current && selectionToken === selectionTokenRef.current) {
        setError(processingErrorMessage(processingError, t));
      }
    } finally {
      if (mountedRef.current && selectionToken === selectionTokenRef.current) setBusy(false);
    }
  }

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file !== undefined) {
      setError(null);
      setEditorFile(file);
    }
  }

  async function handleEditorConfirm(file: File, context?: { ghostScale?: number; sideProfile?: BodyPhotoSide }) {
    setEditorFile(null);
    await processFile(file, context);
  }

  function openCamera() {
    setError(null);
    setCaptureMode("camera");
  }

  function handleCameraFallback(reason: CameraFallbackReason) {
    setCaptureMode("upload");
    setError(t(`bodyPhotos.cameraFallback.${reason}`));
  }

  function handleCameraFile(file: File, context?: { ghostScale?: number; sideProfile?: BodyPhotoSide }) {
    setCaptureMode("upload");
    void processFile(file, context);
  }

  function retake() {
    selectionTokenRef.current += 1;
    clearSelectedPreview(view);
    setProcessed((currentProcessed) => {
      const previous = currentProcessed[view];
      disposeProcessedPhoto(previous);
      const { [view]: _, ...remaining } = currentProcessed;
      processedRef.current = remaining;
      return remaining;
    });
    setError(null);
  }

  async function confirmUpload() {
    if (current === null || !operationalConsent || busy || sessionLoading) return;
    if (loadingExistingSession && session === null) {
      setError(t("bodyPhotos.errors.load"));
      return;
    }
    setBusy(true);
    setError(null);
    let uploadedPhoto = false;
    let uploadedSessionId: string | null = null;
    try {
      const activeSession = session ?? await createBodyPhotoSession(purpose);
      if (session === null) setSession(activeSession);
      const uploaded = await uploadBodyPhoto(activeSession.id, view, current);
      uploadedPhoto = true;
      uploadedSessionId = activeSession.id;
      setSession(uploaded);
      clearSelectedPreview(view);
      if (editingExistingPhoto) {
        await submitBodyPhotoSession(
          activeSession.id,
          true,
          uploaded.model_training_consent?.granted ?? false,
        );
        await startBodyPhotoAnalysis(activeSession.id, true);
        navigate(`/body-progress/${activeSession.id}`);
        return;
      }
      const availableViews = new Set(uploaded.photos.map((photo) => photo.view));
      Object.keys(processed).forEach((item) => availableViews.add(item as BodyPhotoView));
      const missingIndex = views.findIndex((item) => !availableViews.has(item));
      if (missingIndex === -1) {
        setState("confirm");
      } else {
        setCurrentIndex(missingIndex);
      }
    } catch (uploadError) {
      if (uploadedPhoto && editingExistingPhoto && uploadedSessionId !== null) {
        navigate(`/body-progress/${uploadedSessionId}`);
        return;
      }
      setError(
        uploadedPhoto
          ? t("bodyPhotos.errors.analysisNotStarted")
          : uploadErrorMessage(uploadError, t),
      );
    } finally {
      setBusy(false);
    }
  }

  function replaceSelectedPreview(file: File, selectedView: BodyPhotoView) {
    disposeSelectedPreview(selectedPreviewRef.current);
    const next = { view: selectedView, url: URL.createObjectURL(file) };
    selectedPreviewRef.current = next;
    setSelectedPreview(next);
  }

  function clearSelectedPreview(selectedView: BodyPhotoView) {
    const currentPreview = selectedPreviewRef.current;
    if (currentPreview?.view !== selectedView) return;
    disposeSelectedPreview(currentPreview);
    selectedPreviewRef.current = null;
    setSelectedPreview(null);
  }

  async function submit() {
    if (session === null || !complete || !operationalConsent || busy) return;
    setBusy(true);
    setError(null);
    try {
      const submitted = await submitBodyPhotoSession(session.id, true, modelTrainingConsent);
      setSession(submitted);
    } catch {
      setError(t("bodyPhotos.errors.submit"));
      setBusy(false);
      return;
    }
    try {
      await startBodyPhotoAnalysis(session.id, true);
      setState("complete");
    } catch {
      setError(t("bodyPhotos.errors.analysisNotStarted"));
    } finally {
      setBusy(false);
    }
  }

  if (state === "skipped") {
    return (
      <section className="body-photo-wizard body-photo-wizard--status" aria-labelledby="body-photo-title">
        <h1 id="body-photo-title">{t("bodyPhotos.skippedTitle")}</h1>
        <p>{t("bodyPhotos.skippedBody")}</p>
        <Link className="primary-button" to="/dashboard">{t("bodyPhotos.continue")}</Link>
      </section>
    );
  }

  if (state === "complete") {
    return (
      <section className="body-photo-wizard body-photo-wizard--status" aria-labelledby="body-photo-title">
        <p className="eyebrow eyebrow--accent">{t("bodyPhotos.eyebrow")}</p>
        <h1 id="body-photo-title" className="fitsho-display">{t("bodyPhotos.queuedTitle")}</h1>
        <p role="status">{t("bodyPhotos.queuedBody")}</p>
        <button className="primary-button" type="button" onClick={() => navigate("/body-progress")}>{t("bodyPhotos.viewSessions")}</button>
      </section>
    );
  }

  if (!requirementsConfirmed) {
    return (
      <BodyAnalysisRequirementsStep
        onConfirmed={() => setRequirementsConfirmed(true)}
        onCancel={() => navigate("/dashboard")}
      />
    );
  }

  if (state === "confirm") {
    return (
      <section className="body-photo-wizard body-photo-wizard--confirm" aria-labelledby="body-photo-title">
        <div className="body-photo-wizard__heading">
          <div className="body-photo-hud__beacon" aria-hidden="true">
            <span className="body-photo-hud__beacon-dot" />
            <span>BIOMETRIC SCAN REVIEW</span>
          </div>
          <p className="eyebrow eyebrow--accent">{t("bodyPhotos.eyebrow")}</p>
          <h1 id="body-photo-title" className="fitsho-display">{t("bodyPhotos.reviewTitle")}</h1>
        </div>
        <PhotoClothingGuide />
        <div className="body-photo-summary" aria-label={t("bodyPhotos.summaryLabel")}>
          {views.map((item, index) => (
            <button key={item} type="button" className="body-photo-summary__item" onClick={() => {
              setCurrentIndex(index);
              setState("capture");
            }}>
              <div className="body-photo-summary__media">
                <div className="body-photo-hud-stage__corners" aria-hidden="true">
                  <span className="body-photo-hud-stage__corner body-photo-hud-stage__corner--tl" />
                  <span className="body-photo-hud-stage__corner body-photo-hud-stage__corner--tr" />
                  <span className="body-photo-hud-stage__corner body-photo-hud-stage__corner--bl" />
                  <span className="body-photo-hud-stage__corner body-photo-hud-stage__corner--br" />
                </div>
                <img src={photoPreviewUrl(item, processed, session)} alt={t("bodyPhotos.previewAlt", { view: t(`bodyPhotos.views.${item}`) })} />
                <span className="body-photo-summary__badge" aria-hidden="true">✓</span>
              </div>
              <span>{t("bodyPhotos.retake", { view: t(`bodyPhotos.views.${item}`) })}</span>
            </button>
          ))}
        </div>
        <label className="body-photo-consent">
          <input
            type="checkbox"
            checked={operationalConsent}
            onChange={(event) => setOperationalConsent(event.target.checked)}
          />
          <span>{t("bodyPhotos.processingConsentBefore")} <button type="button" className="body-photo-link-button" onClick={() => setTermsOpen(true)}>{t("bodyPhotos.processingTerms")}</button></span>
        </label>
        <label className="body-photo-consent">
          <input
            type="checkbox"
            checked={modelTrainingConsent}
            onChange={(event) => setModelTrainingConsent(event.target.checked)}
          />
          <span>{t("bodyPhotos.modelTraining")}</span>
        </label>
        <p className="body-photo-muted">{t("bodyPhotos.modelTrainingHint")}</p>
        {error !== null && <p className="form-error" role="alert">{error}</p>}
        <button className="primary-button body-photo-submit-btn" type="button" onClick={() => void submit()} disabled={busy || !operationalConsent}>
          {busy ? t("bodyPhotos.submitting") : t("bodyPhotos.submit")}
        </button>
        {termsOpen && <ConsentModal onClose={() => setTermsOpen(false)} />}
      </section>
    );
  }

  return (
    <section className="body-photo-wizard" aria-labelledby="body-photo-title">
      <div className="body-photo-wizard__heading">
        <div className="body-photo-hud__beacon" aria-hidden="true">
          <span className="body-photo-hud__beacon-dot" />
          <span>HUD 3-AXIS SCANNER // 0{currentIndex + 1} OF 03</span>
        </div>
        <p className="eyebrow eyebrow--accent">{t("bodyPhotos.eyebrow")}</p>
        <h1 id="body-photo-title" className="fitsho-display">{t("bodyPhotos.title")}</h1>
        <p>{t("bodyPhotos.optionalIntro")}</p>
        <Link className="body-photo-skip" to="/dashboard" onClick={() => setState("skipped")}>
          {t("bodyPhotos.skip")}
        </Link>
      </div>
      <PhotoClothingGuide />
      <ol className="body-photo-steps" aria-label={t("bodyPhotos.stepsLabel")}>
        {views.map((item, index) => {
          const isCurrent = index === currentIndex;
          const isDone = processed[item] !== undefined || session?.photos.some((photo) => photo.view === item);
          return (
            <li
              key={item}
              aria-current={isCurrent ? "step" : undefined}
              className={`body-photo-steps__item ${isCurrent ? "body-photo-steps__item--active" : ""} ${isDone ? "body-photo-steps__item--done" : ""}`}
            >
              <span className="body-photo-steps__index" aria-hidden="true">0{index + 1}</span>
              <span className="body-photo-steps__label">{t(`bodyPhotos.views.${item}`)}</span>
              {isDone && <span className="body-photo-steps__check" aria-hidden="true">✓</span>}
            </li>
          );
        })}
      </ol>
      <section className="body-photo-capture" aria-labelledby={`body-photo-${view}`}>
        <div className="body-photo-capture__title-row">
          <div>
            <span className="body-photo-capture__badge" aria-hidden="true">
              SCAN VIEW: {view.toUpperCase()}
            </span>
            <h2 id={`body-photo-${view}`}>{t("bodyPhotos.captureTitle", { view: t(`bodyPhotos.views.${view}`) })}</h2>
          </div>
        </div>
        <p>{instructions[view]}</p>
        <p className="body-photo-muted">{t("bodyPhotos.cameraGuidance")}</p>

        {editorFile !== null ? (
          <GhostPhotoEditor
            file={editorFile}
            sex={profileSex}
            sideProfile={sideProfile}
            view={view}
            onConfirm={handleEditorConfirm}
            onCancel={() => setEditorFile(null)}
          />
        ) : (
          <>
            {captureMode === "upload" && <HeadlessPhotoGuide />}
            {view === "side" && (
              <div className="body-photo-stage-toolbar">
                <span className="body-photo-stage-toolbar__label" aria-hidden="true">
                  جهت عکاسی نیمرخ:
                </span>
                <button
                  className="secondary-button body-photo-side-toggle"
                  type="button"
                  aria-label={t("bodyPhotos.sideProfile.toggleLabel", {
                    side: t(`bodyPhotos.sideProfile.${sideProfile}`),
                  })}
                  aria-pressed={sideProfile === "left"}
                  onClick={() => setSideProfile((current) => current === "right" ? "left" : "right")}
                  disabled={busy || sessionLoading}
                >
                  <AppIcon name="refresh" className="body-photo-btn-icon" />
                  <span>{t(`bodyPhotos.sideProfile.${sideProfile}`)}</span>
                </button>
              </div>
            )}
            <div className="body-photo-hud-stage">
              <div className="body-photo-hud-stage__corners" aria-hidden="true">
                <span className="body-photo-hud-stage__corner body-photo-hud-stage__corner--tl" />
                <span className="body-photo-hud-stage__corner body-photo-hud-stage__corner--tr" />
                <span className="body-photo-hud-stage__corner body-photo-hud-stage__corner--bl" />
                <span className="body-photo-hud-stage__corner body-photo-hud-stage__corner--br" />
              </div>
              <div className="body-photo-hud-stage__reticle" aria-hidden="true">
                <div className="body-photo-hud-stage__crosshair body-photo-hud-stage__crosshair--v" />
                <div className="body-photo-hud-stage__crosshair body-photo-hud-stage__crosshair--h" />
                <div className="body-photo-hud-stage__scanline" />
              </div>

              {captureMode === "camera" ? (
                <GhostCameraCapture
                  sex={profileSex}
                  sideProfile={sideProfile}
                  view={view}
                  onFileCaptured={handleCameraFile}
                  onFallback={handleCameraFallback}
                  onClose={() => setCaptureMode("upload")}
                />
              ) : (
                <div className="body-photo-capture-deck">
                  <div className="body-photo-hud-stage__guide-frame" aria-hidden="true">
                    <img
                      src={ghostSilhouetteUrl}
                      alt=""
                      className={`body-photo-hud-stage__silhouette ${view === "side" && sideProfile === "left" ? "body-photo-hud-stage__silhouette--mirrored" : ""}`}
                      style={view === "side" && sideProfile === "left" ? { transform: "scaleX(-1) scale(0.9)" } : undefined}
                    />
                    <span className="body-photo-hud-stage__guide-chip">
                      <AppIcon name="target" className="body-photo-btn-icon" />
                      {view === "side"
                        ? (sideProfile === "left" ? "LEFT PROFILE // نیمرخ چپ" : "RIGHT PROFILE // نیمرخ راست")
                        : `ALIGNMENT TARGET // ${view.toUpperCase()}`}
                    </span>
                  </div>

                  <div className="body-photo-source-actions">
                    <button
                      className="secondary-button body-photo-camera-btn"
                      type="button"
                      onClick={openCamera}
                      disabled={busy || sessionLoading}
                    >
                      <AppIcon name="camera" className="body-photo-btn-icon" />
                      <span>{t("bodyPhotos.useCamera")}</span>
                    </button>
                    <label className="body-photo-upload-control">
                      <span className="body-photo-upload-control__icon" aria-hidden="true">
                        <AppIcon name="sparkles" />
                      </span>
                      <span className="body-photo-upload-control__title">
                        {t("bodyPhotos.uploadExistingPhoto", { view: t(`bodyPhotos.views.${view}`) })}
                      </span>
                      <span className="body-photo-upload-control__hint" aria-hidden="true">
                        JPG, PNG, WebP
                      </span>
                      <input
                        aria-label={t("bodyPhotos.inputLabel", { view: t(`bodyPhotos.views.${view}`) })}
                        accept="image/jpeg,image/png,image/webp"
                        type="file"
                        onChange={selectFile}
                        disabled={busy || sessionLoading}
                      />
                    </label>
                  </div>
                </div>
              )}
            </div>

            {selectedPreview?.view === view && (
              <div className="body-photo-source-preview">
                <div className="body-photo-preview__frame">
                  <div className="body-photo-hud-stage__corners" aria-hidden="true">
                    <span className="body-photo-hud-stage__corner body-photo-hud-stage__corner--tl" />
                    <span className="body-photo-hud-stage__corner body-photo-hud-stage__corner--tr" />
                    <span className="body-photo-hud-stage__corner body-photo-hud-stage__corner--bl" />
                    <span className="body-photo-hud-stage__corner body-photo-hud-stage__corner--br" />
                  </div>
                  <img
                    src={selectedPreview.url}
                    alt={t("bodyPhotos.selectedPreviewAlt", { view: t(`bodyPhotos.views.${view}`) })}
                  />
                  {busy && (
                    <div className="body-photo-preview__scan-overlay" aria-hidden="true">
                      <span className="body-analysis-spinner" />
                      <span>{t("bodyPhotos.preparing")}</span>
                    </div>
                  )}
                </div>
                <p>{t("bodyPhotos.selectedPreview")}</p>
              </div>
            )}
            {current !== null && (
              <div className="body-photo-preview">
                <div className="body-photo-preview__frame">
                  <div className="body-photo-hud-stage__corners" aria-hidden="true">
                    <span className="body-photo-hud-stage__corner body-photo-hud-stage__corner--tl" />
                    <span className="body-photo-hud-stage__corner body-photo-hud-stage__corner--tr" />
                    <span className="body-photo-hud-stage__corner body-photo-hud-stage__corner--bl" />
                    <span className="body-photo-hud-stage__corner body-photo-hud-stage__corner--br" />
                  </div>
                  <img src={current.previewUrl} alt={t("bodyPhotos.previewAlt", { view: t(`bodyPhotos.views.${view}`) })} />
                  <div className="body-photo-preview__shield-tag" aria-hidden="true">
                    <AppIcon name="shield" className="body-photo-btn-icon" />
                    <span>ANONYMIZED & BIOMETRIC READY</span>
                  </div>
                </div>
                <p>{t("bodyPhotos.anonymizedPreview")}</p>
                <PhotoQualityFeedback photo={current} />
                <button type="button" className="secondary-button body-photo-retake-btn" onClick={retake} disabled={busy}>
                  <AppIcon name="refresh" className="body-photo-btn-icon" />
                  <span>{t("bodyPhotos.retake", { view: t(`bodyPhotos.views.${view}`) })}</span>
                </button>
              </div>
            )}
            <label className="body-photo-consent">
              <input
                type="checkbox"
                checked={operationalConsent}
                onChange={(event) => setOperationalConsent(event.target.checked)}
              />
              <span>{t("bodyPhotos.processingConsentBefore")} <button type="button" className="body-photo-link-button" onClick={() => setTermsOpen(true)}>{t("bodyPhotos.processingTerms")}</button></span>
            </label>
            {error !== null && <p className="form-error" role="alert">{error}</p>}
            <button className="primary-button body-photo-confirm-btn" type="button" onClick={() => void confirmUpload()} disabled={current === null || !operationalConsent || busy || sessionLoading}>
              {busy ? t("bodyPhotos.preparing") : t("bodyPhotos.confirmUpload", { view: t(`bodyPhotos.views.${view}`) })}
            </button>
          </>
        )}
      </section>
      {termsOpen && <ConsentModal onClose={() => setTermsOpen(false)} />}
    </section>
  );
}

function PhotoClothingGuide() {
  const { t } = useTranslation();
  return (
    <aside className="body-photo-clothing-guide" aria-label={t("bodyPhotos.clothingTitle")}>
      <div className="body-photo-clothing-guide__header">
        <span className="body-photo-clothing-guide__icon" aria-hidden="true">⚡</span>
        <strong>{t("bodyPhotos.clothingTitle")}</strong>
      </div>
      <p>{t("bodyPhotos.clothingBody")}</p>
      <p>{t("bodyPhotos.coverage")}</p>
    </aside>
  );
}

function HeadlessPhotoGuide() {
  const { t } = useTranslation();
  const retained = ["shouldersArms", "waistHips", "legsKnees", "anklesFeet"] as const;
  return (
    <aside className="body-photo-headless-guide" aria-label={t("bodyPhotos.headlessGuideLabel")}>
      <div className="body-photo-headless-guide__header">
        <span className="body-photo-headless-guide__badge" aria-hidden="true">
          <AppIcon name="shield" className="body-photo-btn-icon" />
        </span>
        <div>
          <strong>{t("bodyPhotos.headlessInstruction")}</strong>
          <p>{t("bodyPhotos.headlessGuideIntro")}</p>
        </div>
      </div>
      <ul>
        {retained.map((item) => (
          <li key={item}>
            <span className="body-photo-headless-guide__check" aria-hidden="true">✓</span>
            <span>{t(`bodyPhotos.retained.${item}`)}</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}

function PhotoQualityFeedback({ photo }: { photo: ProcessedBodyPhoto }) {
  const { t } = useTranslation();
  const { quality, warnings } = photo.validation;
  return (
    <section className="body-photo-quality" aria-label={t("bodyPhotos.quality.title")}>
      <div className="body-photo-quality__header">
        <span className="body-photo-quality__beacon" aria-hidden="true" />
        <strong>{t("bodyPhotos.quality.title")}</strong>
        <span className="body-photo-quality__badge">AI VISION VERIFIED</span>
      </div>
      <dl>
        <div>
          <dt>{t("bodyPhotos.quality.lighting")}</dt>
          <dd>
            <span className="body-photo-quality__gauge" aria-hidden="true">
              <span className="body-photo-quality__gauge-fill" style={{ width: `${Math.round(quality.brightnessScore * 100)}%` }} />
            </span>
            <span>{formatScore(quality.brightnessScore)}</span>
          </dd>
        </div>
        <div>
          <dt>{t("bodyPhotos.quality.sharpness")}</dt>
          <dd>
            <span className="body-photo-quality__gauge" aria-hidden="true">
              <span className="body-photo-quality__gauge-fill" style={{ width: `${Math.round(quality.sharpnessScore * 100)}%` }} />
            </span>
            <span>{formatScore(quality.sharpnessScore)}</span>
          </dd>
        </div>
        <div>
          <dt>{t("bodyPhotos.quality.landmarks")}</dt>
          <dd>
            <span className="body-photo-quality__gauge" aria-hidden="true">
              <span className="body-photo-quality__gauge-fill" style={{ width: `${Math.round(quality.minimumLandmarkVisibility * 100)}%` }} />
            </span>
            <span>{formatScore(quality.minimumLandmarkVisibility)}</span>
          </dd>
        </div>
      </dl>
      {warnings && warnings.length > 0 && (
        <aside className="body-photo-quality__warnings" aria-label={t("bodyPhotos.validationWarnings.title")}>
          <strong className="body-photo-quality__warnings-title">{t("bodyPhotos.validationWarnings.title")}</strong>
          <ul>
            {warnings.map((warning) => (
              <li key={warning}>{t(`bodyPhotos.validationWarnings.${warning}`)}</li>
            ))}
          </ul>
        </aside>
      )}
    </section>
  );
}

function processingErrorMessage(error: unknown, t: ReturnType<typeof useTranslation>["t"]): string {
  if (error instanceof BodyPhotoProcessingError) {
    return t(`bodyPhotos.errors.${error.code}`, { defaultValue: t("bodyPhotos.errors.processing") });
  }
  return t("bodyPhotos.errors.processing");
}

function uploadErrorMessage(error: unknown, t: ReturnType<typeof useTranslation>["t"]): string {
  if (
    error instanceof ApiError
    && error.status === 403
    && error.message === "Untrusted request origin"
  ) {
    return t("bodyPhotos.errors.untrustedOrigin");
  }
  if (error instanceof ApiError && error.code !== null) {
    return t(`bodyPhotos.errors.${error.code}`, { defaultValue: t("bodyPhotos.errors.upload") });
  }
  return t("bodyPhotos.errors.upload");
}

function formatScore(score: number): string {
  return `${Math.round(score * 100)}%`;
}

function photoPreviewUrl(
  view: BodyPhotoView,
  processed: Partial<Record<BodyPhotoView, ProcessedBodyPhoto>>,
  session: BodyPhotoSession | null,
): string {
  return processed[view]?.previewUrl
    ?? session?.photos.find((photo) => photo.view === view)?.content_url
    ?? "";
}

function disposeProcessedPhoto(photo: ProcessedBodyPhoto | undefined) {
  if (photo !== undefined) URL.revokeObjectURL(photo.previewUrl);
}

function disposeSelectedPreview(preview: SelectedPhotoPreview | null) {
  if (preview !== null) URL.revokeObjectURL(preview.url);
}

function ConsentModal({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="body-photo-modal-backdrop" role="presentation">
      <section className="body-photo-modal" role="dialog" aria-modal="true" aria-labelledby="body-photo-terms-title">
        <h2 id="body-photo-terms-title">{t("bodyPhotos.termsTitle")}</h2>
        <p>{t("bodyPhotos.termsOptional")}</p>
        <p>{t("bodyPhotos.termsStorage")}</p>
        <p>{t("bodyPhotos.termsNoDiagnosis")}</p>
        <p>{t("bodyPhotos.termsTraining")}</p>
        <button className="secondary-button" type="button" onClick={onClose}>{t("bodyPhotos.close")}</button>
      </section>
    </div>
  );
}
