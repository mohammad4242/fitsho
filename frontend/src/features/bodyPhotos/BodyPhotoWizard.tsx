import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";

import {
  createBodyPhotoSession,
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

export function BodyPhotoWizard({
  processor = browserBodyPhotoProcessor,
  purpose = "initial_plan",
}: {
  processor?: BodyPhotoProcessor;
  purpose?: BodyPhotoPurpose;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [currentIndex, setCurrentIndex] = useState(0);
  const [processed, setProcessed] = useState<Partial<Record<BodyPhotoView, ProcessedBodyPhoto>>>({});
  const [session, setSession] = useState<BodyPhotoSession | null>(null);
  const [operationalConsent, setOperationalConsent] = useState(false);
  const [modelTrainingConsent, setModelTrainingConsent] = useState(false);
  const [state, setState] = useState<WizardState>("capture");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [termsOpen, setTermsOpen] = useState(false);
  const processedRef = useRef(processed);
  const mountedRef = useRef(false);
  const selectionTokenRef = useRef(0);

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
      processedRef.current = {};
    };
  }, []);

  const instructions = useMemo(() => ({
    front: t("bodyPhotos.pose.front"),
    side: t("bodyPhotos.pose.side"),
    back: t("bodyPhotos.pose.back"),
  }), [t]);

  async function selectFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file === undefined || busy) return;
    const selectedView = view;
    const selectionToken = ++selectionTokenRef.current;
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
      event.target.value = "";
      if (mountedRef.current && selectionToken === selectionTokenRef.current) setBusy(false);
    }
  }

  function retake() {
    selectionTokenRef.current += 1;
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
    if (current === null || !operationalConsent || busy) return;
    setBusy(true);
    setError(null);
    try {
      const activeSession = session ?? await createBodyPhotoSession(purpose);
      if (session === null) setSession(activeSession);
      const uploaded = await uploadBodyPhoto(activeSession.id, view, current);
      setSession(uploaded);
      if (currentIndex === views.length - 1) {
        setState("confirm");
      } else {
        setCurrentIndex((index) => index + 1);
      }
    } catch {
      setError(t("bodyPhotos.errors.upload"));
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (session === null || !complete || !operationalConsent || busy) return;
    setBusy(true);
    setError(null);
    try {
      const submitted = await submitBodyPhotoSession(session.id, true, modelTrainingConsent);
      setSession(submitted);
      await startBodyPhotoAnalysis(submitted.id);
      setState("complete");
    } catch {
      setError(t("bodyPhotos.errors.submit"));
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
        <label className="body-photo-upload-control">
          <span>{t("bodyPhotos.selectPhoto", { view: t(`bodyPhotos.views.${view}`) })}</span>
          <input
            aria-label={t("bodyPhotos.inputLabel", { view: t(`bodyPhotos.views.${view}`) })}
            accept="image/jpeg,image/png,image/webp"
            capture="environment"
            type="file"
            onChange={(event) => void selectFile(event)}
            disabled={busy}
          />
        </label>
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
        <button className="primary-button" type="button" onClick={() => void confirmUpload()} disabled={current === null || !operationalConsent || busy}>
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

function PhotoQualityFeedback({ photo }: { photo: ProcessedBodyPhoto }) {
  const { t } = useTranslation();
  const { quality, warnings } = photo.validation;
  return (
    <section className="body-photo-quality" aria-label={t("bodyPhotos.quality.title")}>
      <strong>{t("bodyPhotos.quality.title")}</strong>
      <dl>
        <div><dt>{t("bodyPhotos.quality.overall")}</dt><dd>{formatScore(quality.overallScore)}</dd></div>
        <div><dt>{t("bodyPhotos.quality.lighting")}</dt><dd>{formatScore(quality.brightnessScore)}</dd></div>
        <div><dt>{t("bodyPhotos.quality.sharpness")}</dt><dd>{formatScore(quality.sharpnessScore)}</dd></div>
        <div><dt>{t("bodyPhotos.quality.pose")}</dt><dd>{formatScore(quality.poseScore)}</dd></div>
      </dl>
      {warnings.length > 0 && <p className="body-photo-muted">{t("bodyPhotos.quality.warning")}</p>}
    </section>
  );
}

function processingErrorMessage(error: unknown, t: ReturnType<typeof useTranslation>["t"]): string {
  if (error instanceof BodyPhotoProcessingError) {
    return t(`bodyPhotos.errors.${error.code}`, { defaultValue: t("bodyPhotos.errors.processing") });
  }
  return t("bodyPhotos.errors.processing");
}

function formatScore(score: number): string {
  return `${Math.round(score * 100)}%`;
}

function disposeProcessedPhoto(photo: ProcessedBodyPhoto | undefined) {
  if (photo !== undefined) URL.revokeObjectURL(photo.previewUrl);
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
