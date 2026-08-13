import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "../../shared/apiClient";

import {
  createBodyPhotoSession,
  getBodyPhotoSession,
  startBodyPhotoAnalysis,
  submitBodyPhotoSession,
  uploadBodyPhoto,
} from "./api";
import {
  browserBodyPhotoProcessor,
  BodyPhotoProcessingError,
  type BodyPhotoProcessor,
  type ProcessedBodyPhoto,
} from "./processor";
import type { BodyPhotoPurpose, BodyPhotoSession, BodyPhotoView } from "./types";
import "./bodyPhotos.css";

const views: BodyPhotoView[] = ["front", "side", "back"];

type WizardState = "capture" | "confirm" | "complete" | "skipped";

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
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const editSessionId = searchParams.get("sessionId");
  const editView = views.find((item) => item === searchParams.get("view")) ?? null;
  const editingExistingPhoto = editSessionId !== null && editView !== null;
  const [currentIndex, setCurrentIndex] = useState(() => editView === null ? 0 : views.indexOf(editView));
  const [processed, setProcessed] = useState<Partial<Record<BodyPhotoView, ProcessedBodyPhoto>>>({});
  const [session, setSession] = useState<BodyPhotoSession | null>(null);
  const [operationalConsent, setOperationalConsent] = useState(false);
  const [modelTrainingConsent, setModelTrainingConsent] = useState(false);
  const [state, setState] = useState<WizardState>("capture");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [termsOpen, setTermsOpen] = useState(false);
  const [selectedPreview, setSelectedPreview] = useState<SelectedPhotoPreview | null>(null);
  const processedRef = useRef(processed);
  const selectedPreviewRef = useRef<SelectedPhotoPreview | null>(null);
  const mountedRef = useRef(false);
  const selectionTokenRef = useRef(0);
  const [sessionLoading, setSessionLoading] = useState(editingExistingPhoto);

  const view = views[currentIndex];
  const current = processed[view] ?? null;
  const complete = views.every((item) => processed[item] !== undefined);

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
    if (!editingExistingPhoto || editSessionId === null) return;
    void getBodyPhotoSession(editSessionId)
      .then((loaded) => {
        if (!mountedRef.current) return;
        setSession(loaded);
        setOperationalConsent(loaded.operational_processing_consent?.granted ?? false);
        setModelTrainingConsent(loaded.model_training_consent?.granted ?? false);
      })
      .catch(() => {
        if (mountedRef.current) setError(t("bodyPhotos.errors.load"));
      })
      .finally(() => {
        if (mountedRef.current) setSessionLoading(false);
      });
  }, [editSessionId, editingExistingPhoto, t]);

  const instructions = useMemo(() => ({
    front: t("bodyPhotos.pose.front"),
    side: t("bodyPhotos.pose.side"),
    back: t("bodyPhotos.pose.back"),
  }), [t]);

  async function processFile(file: File) {
    if (busy) return;
    const selectedView = view;
    const selectionToken = ++selectionTokenRef.current;
    replaceSelectedPreview(file, selectedView);
    setBusy(true);
    setError(null);
    try {
      const next = await processor.process(file, selectedView);
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
    if (file !== undefined) void processFile(file);
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
    if (editingExistingPhoto && session === null) {
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
        await startBodyPhotoAnalysis(activeSession.id);
        navigate(`/body-progress/${activeSession.id}`);
        return;
      }
      if (currentIndex === views.length - 1) {
        setState("confirm");
      } else {
        setCurrentIndex((index) => index + 1);
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
      await startBodyPhotoAnalysis(session.id);
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

  if (state === "confirm") {
    return (
      <section className="body-photo-wizard" aria-labelledby="body-photo-title">
        <p className="eyebrow eyebrow--accent">{t("bodyPhotos.eyebrow")}</p>
        <h1 id="body-photo-title" className="fitsho-display">{t("bodyPhotos.reviewTitle")}</h1>
        <PhotoClothingGuide />
        <div className="body-photo-summary" aria-label={t("bodyPhotos.summaryLabel")}>
          {views.map((item, index) => (
            <button key={item} type="button" className="body-photo-summary__item" onClick={() => {
              setCurrentIndex(index);
              setState("capture");
            }}>
              <img src={processed[item]?.previewUrl} alt={t("bodyPhotos.previewAlt", { view: t(`bodyPhotos.views.${item}`) })} />
              <span>{t("bodyPhotos.retake", { view: t(`bodyPhotos.views.${item}`) })}</span>
            </button>
          ))}
        </div>
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
        <button className="primary-button" type="button" onClick={() => void submit()} disabled={busy}>
          {busy ? t("bodyPhotos.submitting") : t("bodyPhotos.submit")}
        </button>
      </section>
    );
  }

  return (
    <section className="body-photo-wizard" aria-labelledby="body-photo-title">
      <div className="body-photo-wizard__heading">
        <p className="eyebrow eyebrow--accent">{t("bodyPhotos.eyebrow")}</p>
        <h1 id="body-photo-title" className="fitsho-display">{t("bodyPhotos.title")}</h1>
        <p>{t("bodyPhotos.optionalIntro")}</p>
        <Link className="body-photo-skip" to="/dashboard" onClick={() => setState("skipped")}>
          {t("bodyPhotos.skip")}
        </Link>
      </div>
      <PhotoClothingGuide />
      <ol className="body-photo-steps" aria-label={t("bodyPhotos.stepsLabel")}>
        {views.map((item, index) => <li key={item} aria-current={index === currentIndex ? "step" : undefined}>{t(`bodyPhotos.views.${item}`)}</li>)}
      </ol>
      <section className="body-photo-capture" aria-labelledby={`body-photo-${view}`}>
        <h2 id={`body-photo-${view}`}>{t("bodyPhotos.captureTitle", { view: t(`bodyPhotos.views.${view}`) })}</h2>
        <p>{instructions[view]}</p>
        <p className="body-photo-muted">{t("bodyPhotos.cameraGuidance")}</p>
        <HeadlessPhotoGuide />
        <div className="body-photo-source-actions">
          <label className="body-photo-upload-control">
            <span>{t("bodyPhotos.uploadExistingPhoto", { view: t(`bodyPhotos.views.${view}`) })}</span>
            <input
              aria-label={t("bodyPhotos.inputLabel", { view: t(`bodyPhotos.views.${view}`) })}
              accept="image/jpeg,image/png,image/webp"
              type="file"
              onChange={selectFile}
              disabled={busy || sessionLoading}
            />
          </label>
        </div>
        {selectedPreview?.view === view && (
          <div className="body-photo-source-preview">
            <img
              src={selectedPreview.url}
              alt={t("bodyPhotos.selectedPreviewAlt", { view: t(`bodyPhotos.views.${view}`) })}
            />
            <p>{t("bodyPhotos.selectedPreview")}</p>
          </div>
        )}
        {current !== null && (
          <div className="body-photo-preview">
            <img src={current.previewUrl} alt={t("bodyPhotos.previewAlt", { view: t(`bodyPhotos.views.${view}`) })} />
            <p>{t("bodyPhotos.anonymizedPreview")}</p>
            <PhotoQualityFeedback photo={current} />
            <button type="button" className="secondary-button" onClick={retake} disabled={busy}>
              {t("bodyPhotos.retake", { view: t(`bodyPhotos.views.${view}`) })}
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
        <button className="primary-button" type="button" onClick={() => void confirmUpload()} disabled={current === null || !operationalConsent || busy || sessionLoading}>
          {busy ? t("bodyPhotos.preparing") : t("bodyPhotos.confirmUpload", { view: t(`bodyPhotos.views.${view}`) })}
        </button>
      </section>
      {termsOpen && <ConsentModal onClose={() => setTermsOpen(false)} />}
    </section>
  );
}

function PhotoClothingGuide() {
  const { t } = useTranslation();
  return <aside className="body-photo-clothing-guide" aria-label={t("bodyPhotos.clothingTitle")}><strong>{t("bodyPhotos.clothingTitle")}</strong><p>{t("bodyPhotos.clothingBody")}</p><p>{t("bodyPhotos.coverage")}</p></aside>;
}

function HeadlessPhotoGuide() {
  const { t } = useTranslation();
  const retained = ["shouldersArms", "waistHips", "legsKnees", "anklesFeet"] as const;
  return (
    <aside className="body-photo-headless-guide" aria-label={t("bodyPhotos.headlessGuideLabel")}>
      <strong>{t("bodyPhotos.headlessInstruction")}</strong>
      <p>{t("bodyPhotos.headlessGuideIntro")}</p>
      <ul>
        {retained.map((item) => <li key={item}>{t(`bodyPhotos.retained.${item}`)}</li>)}
      </ul>
    </aside>
  );
}

function PhotoQualityFeedback({ photo }: { photo: ProcessedBodyPhoto }) {
  const { t } = useTranslation();
  const { quality } = photo.validation;
  return (
    <section className="body-photo-quality" aria-label={t("bodyPhotos.quality.title")}>
      <strong>{t("bodyPhotos.quality.title")}</strong>
      <dl>
        <div><dt>{t("bodyPhotos.quality.lighting")}</dt><dd>{formatScore(quality.brightnessScore)}</dd></div>
        <div><dt>{t("bodyPhotos.quality.sharpness")}</dt><dd>{formatScore(quality.sharpnessScore)}</dd></div>
        <div><dt>{t("bodyPhotos.quality.landmarks")}</dt><dd>{formatScore(quality.minimumLandmarkVisibility)}</dd></div>
      </dl>
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
