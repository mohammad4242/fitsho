import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import {
  getBodyPhotoComparison,
  getBodyPhotoAnalysis,
  getBodyPhotoSession,
  retryBodyPhotoAnalysis,
  startBodyPhotoAnalysis,
} from "./api";
import { BodyAnalysisResult } from "./BodyAnalysisResult";
import { ProgressComparison } from "./ProgressComparison";
import type { BodyAnalysis, BodyPhotoSession } from "./types";
import "./bodyPhotos.css";

const activeAnalysisStates = new Set(["queued", "validating", "analyzing"]);

export function BodyAnalysisResultPage() {
  const { t, i18n } = useTranslation();
  const { sessionId } = useParams();
  const [session, setSession] = useState<BodyPhotoSession | null>(null);
  const [analysis, setAnalysis] = useState<BodyAnalysis | null>(null);
  const [comparison, setComparison] = useState<Awaited<ReturnType<typeof getBodyPhotoComparison>>>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [analysisActionFailed, setAnalysisActionFailed] = useState(false);

  const load = useCallback(async () => {
    if (sessionId === undefined) {
      setFailed(true);
      setLoading(false);
      return;
    }
    try {
      const [loadedSession, loadedAnalysis, loadedComparison] = await Promise.all([
        getBodyPhotoSession(sessionId),
        getBodyPhotoAnalysis(sessionId),
        getBodyPhotoComparison(sessionId).catch(() => null),
      ]);
      setSession(loadedSession);
      let effectiveAnalysis = loadedAnalysis;
      if (effectiveAnalysis === null && loadedSession.state === "queued") {
        try {
          effectiveAnalysis = await startBodyPhotoAnalysis(sessionId);
          setAnalysisActionFailed(false);
        } catch {
          setAnalysisActionFailed(true);
        }
      }
      setAnalysis(effectiveAnalysis);
      setComparison(loadedComparison);
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (sessionId === undefined || analysis === null || !activeAnalysisStates.has(analysis.status)) {
      return;
    }
    const timer = window.setTimeout(() => {
      void getBodyPhotoAnalysis(sessionId)
        .then((next) => {
          if (next !== null) {
            setAnalysis(next);
            if (next.normalized_result !== null) {
              void getBodyPhotoComparison(sessionId)
                .then(setComparison)
                .catch(() => undefined);
            }
          }
        })
        .catch(() => undefined);
    }, 3000);
    return () => window.clearTimeout(timer);
  }, [analysis, sessionId]);

  async function retry() {
    if (sessionId === undefined || actionBusy) return;
    setActionBusy(true);
    try {
      const next = analysis?.status === "failed"
        ? await retryBodyPhotoAnalysis(sessionId)
        : await startBodyPhotoAnalysis(sessionId);
      setAnalysis(next);
      if (next.normalized_result !== null) {
        void getBodyPhotoComparison(sessionId)
          .then(setComparison)
          .catch(() => undefined);
      }
      setAnalysisActionFailed(false);
    } catch {
      setAnalysisActionFailed(true);
    } finally {
      setActionBusy(false);
    }
  }

  if (loading) {
    return <main className="body-analysis-page fitsho-page"><p role="status">{t("bodyPhotos.results.loading")}</p></main>;
  }
  if (failed || session === null) {
    return (
      <main className="body-analysis-page fitsho-page">
        <p className="form-error" role="alert">{t("bodyPhotos.results.loadError")}</p>
        <button className="secondary-button" type="button" onClick={() => {
          setLoading(true);
          void load();
        }}>{t("common.retry")}</button>
      </main>
    );
  }

  const locale = i18n.resolvedLanguage === "en" ? "en" : "fa-IR";
  const sessionDate = new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(session.created_at));
  const failedAnalysisMessage = analysis?.error_code === null || analysis?.error_code === undefined
    ? analysis?.safe_error_message ?? t("bodyPhotos.results.failedSafe")
    : t(`bodyPhotos.results.providerErrors.${analysis.error_code}`, {
      defaultValue: analysis.safe_error_message ?? t("bodyPhotos.results.failedSafe"),
    });

  return (
    <main className="body-analysis-page fitsho-page">
      <header className="body-analysis-page__header">
        <p className="eyebrow eyebrow--accent">{t("bodyPhotos.eyebrow")}</p>
        <h1 className="fitsho-display">{t("bodyPhotos.results.title")}</h1>
        <p>{t("bodyPhotos.results.sessionDate", { date: sessionDate })}</p>
      </header>

      {analysis === null && !analysisActionFailed && (
        <p role="status">{t("bodyPhotos.results.notStarted")}</p>
      )}
      {analysisActionFailed && analysis?.status !== "failed" && (
        <section className="body-analysis-status body-analysis-status--failed" role="alert">
          <div>
            <strong>{t("bodyPhotos.results.analysisStatus.failed")}</strong>
            <p>{t("bodyPhotos.results.failedSafe")}</p>
          </div>
          <button className="secondary-button" type="button" disabled={actionBusy} onClick={() => void retry()}>
            {t("bodyPhotos.results.retry")}
          </button>
        </section>
      )}
      {analysis !== null && activeAnalysisStates.has(analysis.status) && (
        <section className="body-analysis-status" role="status">
          <span className="body-analysis-spinner" aria-hidden="true" />
          <div>
            <strong>{t(`bodyPhotos.results.analysisStatus.${analysis.status}`)}</strong>
            <p>{t("bodyPhotos.results.processingHelp")}</p>
          </div>
        </section>
      )}
      {analysis?.status === "failed" && (
        <section className="body-analysis-status body-analysis-status--failed" role="alert">
          <div>
            <strong>{t("bodyPhotos.results.analysisStatus.failed")}</strong>
            <p>{failedAnalysisMessage}</p>
            {analysis.photo_validation?.issues.map((issue) => (
              <div className="body-analysis-status__issue" key={issue.view}>
                <p>
                  <strong>{t(`bodyPhotos.views.${issue.view}`)}: </strong>
                  {issue.reasons.map((reason) => t(`bodyPhotos.results.photoValidation.${reason}`)).join(" · ")}
                </p>
                <Link
                  className="body-photo-link-button"
                  to={`/body-progress/new?sessionId=${session.id}&view=${issue.view}`}
                >
                  {t("bodyPhotos.results.editPhoto", {
                    view: t(`bodyPhotos.views.${issue.view}`),
                  })}
                </Link>
              </div>
            ))}
          </div>
          <button className="secondary-button" type="button" disabled={actionBusy} onClick={() => void retry()}>
            {t("bodyPhotos.results.retry")}
          </button>
        </section>
      )}

      {analysis !== null && <BodyAnalysisResult analysis={analysis} />}
      {comparison !== null && <ProgressComparison comparison={comparison} />}
      <details className="body-analysis-photo-details">
        <summary>{t("bodyPhotos.results.photosLabel")}</summary>
        <section className="body-analysis-photos" aria-label={t("bodyPhotos.results.photosLabel")}>
          {session.photos.map((photo) => <figure key={photo.id}><img src={photo.content_url} alt={t("bodyPhotos.results.photoAlt", { view: t(`bodyPhotos.views.${photo.view}`) })} /><figcaption>{t(`bodyPhotos.views.${photo.view}`)}</figcaption></figure>)}
        </section>
      </details>
      {analysis?.normalized_result !== null && analysis?.normalized_result !== undefined && (
        <Link className="primary-button body-analysis-plan-link" to="/workout-plan">
          {t("bodyPhotos.results.viewWorkoutPlan")}
        </Link>
      )}
    </main>
  );
}
