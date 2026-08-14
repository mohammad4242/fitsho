import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { AppIcon } from "../../shared/AppIcon";
import { deleteBodyPhotoSession, getBodyPhotoSessions } from "./api";
import type { BodyPhotoSession } from "./types";
import "./bodyPhotos.css";

export function BodyProgressPage() {
  const { t, i18n } = useTranslation();
  const l = (fa: string, en: string) => i18n.resolvedLanguage === "en" ? en : fa;
  const [sessions, setSessions] = useState<BodyPhotoSession[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<BodyPhotoSession | null>(null);
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);
  const [deleteFailed, setDeleteFailed] = useState(false);
  const deleteTriggerRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    void getBodyPhotoSessions()
      .then((response) => setSessions(response.items))
      .catch(() => setFailed(true));
  }, []);

  useEffect(() => {
    if (deleteTarget === null) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape" || deletingSessionId !== null) return;
      event.preventDefault();
      setDeleteTarget(null);
      setDeleteFailed(false);
      deleteTriggerRef.current?.focus();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [deleteTarget, deletingSessionId]);

  const incompleteSessions = sessions?.filter((session) => session.submitted_at === null) ?? [];
  const analysisSessions = sessions?.filter((session) => session.submitted_at !== null) ?? [];
  const locale = i18n.resolvedLanguage === "en" ? "en" : "fa-IR";

  function openDeleteDialog(session: BodyPhotoSession, trigger: HTMLButtonElement) {
    deleteTriggerRef.current = trigger;
    setDeleteFailed(false);
    setDeleteTarget(session);
  }

  function closeDeleteDialog() {
    if (deletingSessionId !== null) return;
    setDeleteTarget(null);
    setDeleteFailed(false);
    deleteTriggerRef.current?.focus();
  }

  async function removeSession() {
    if (deleteTarget === null) return;
    const sessionId = deleteTarget.id;
    setDeletingSessionId(sessionId);
    setDeleteFailed(false);
    try {
      await deleteBodyPhotoSession(sessionId);
      setSessions((current) => current?.filter((session) => session.id !== sessionId) ?? current);
      setDeleteTarget(null);
    } catch {
      setDeleteFailed(true);
    } finally {
      setDeletingSessionId(null);
    }
  }

  return (
    <main className="body-analysis-home fitsho-page">
      <header className="body-analysis-home__header">
        <h1 dir="ltr">Body Analysis</h1>
        <p>{t("bodyPhotos.optionalIntro")}</p>
      </header>

      <figure className="body-analysis-visual">
        <img
          alt={t("bodyPhotos.mainVisualAlt")}
          height="1842"
          loading="eager"
          src="/body-analysis/Bod.png"
          width="854"
        />
        <span className="body-analysis-visual__scan-line" aria-hidden="true" />
        <figcaption>
          <span aria-hidden="true" />
          {t("bodyPhotos.scannerLabel")}
        </figcaption>
      </figure>

      {sessions === null && !failed && (
        <p className="body-analysis-home__status" role="status">{t("bodyPhotos.loading")}</p>
      )}
      {failed && <p className="form-error body-analysis-home__status" role="alert">{t("bodyPhotos.errors.load")}</p>}

      {sessions?.length === 0 && (
        <section className="body-analysis-empty" aria-labelledby="body-analysis-empty-title">
          <span className="body-analysis-empty__icon" aria-hidden="true"><AppIcon name="camera" /></span>
          <h2 id="body-analysis-empty-title">{t("bodyPhotos.emptyTitle")}</h2>
          <p>{t("bodyPhotos.emptyBody")}</p>
          <Link className="primary-button" to="/body-progress/new">{t("bodyPhotos.emptyAction")}</Link>
        </section>
      )}

      {incompleteSessions.length > 0 && (
        <section className="body-analysis-history body-analysis-incomplete" aria-labelledby="body-analysis-incomplete-title">
          <header>
            <div>
              <p>{t("bodyPhotos.incomplete.eyebrow")}</p>
              <h2 id="body-analysis-incomplete-title">{t("bodyPhotos.incomplete.title")}</h2>
            </div>
            {analysisSessions.length === 0 && (
              <Link className="primary-button" to="/body-progress/new">{t("bodyPhotos.start")}</Link>
            )}
          </header>
          <ul aria-label={t("bodyPhotos.incomplete.title")}>
            {incompleteSessions.map((session) => (
              <li className="body-analysis-session body-analysis-session--incomplete" key={session.id}>
                <div className="body-analysis-session__details">
                  <strong>{new Intl.DateTimeFormat(locale).format(new Date(session.created_at))}</strong>
                  <span>{t(`bodyPhotos.status.${session.state}`)}</span>
                </div>
                <span>{session.photos.length}/3</span>
                <div className="body-analysis-session__actions">
                  <Link to={`/body-progress/new?sessionId=${session.id}`}>{t("bodyPhotos.incomplete.continue")}</Link>
                  <button
                    type="button"
                    onClick={(event) => openDeleteDialog(session, event.currentTarget)}
                  >
                    {t("bodyPhotos.deleteDialog.deleteUpload")}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {analysisSessions.length > 0 && (
        <section className="body-analysis-history" aria-labelledby="body-analysis-history-title">
          <header>
            <div>
              <p>{t("bodyPhotos.scannerLabel")}</p>
              <h2 id="body-analysis-history-title">{t("bodyPhotos.historyTitle")}</h2>
            </div>
            <Link className="primary-button" to="/body-progress/new">{t("bodyPhotos.start")}</Link>
          </header>
          <ul aria-label={t("bodyPhotos.progressTitle")}>
            {analysisSessions.map((session, index) => (
              <li className={index === 0 ? "body-analysis-session body-analysis-session--latest" : "body-analysis-session"} key={session.id}>
                {index === 0 && session.photos[0] && (
                  <figure><img src={session.photos[0].content_url} alt={l("آخرین عکس تحلیل بدن", "Latest progress photo")} /></figure>
                )}
                <div>
                  {index === 0 && <small>{l("آخرین تحلیل", "Latest analysis")}</small>}
                  <strong>{new Intl.DateTimeFormat(locale).format(new Date(session.created_at))}</strong>
                  <span>{t(`bodyPhotos.status.${session.state}`)}</span>
                </div>
                <span>{session.photos.length}/3</span>
                <div className="body-analysis-session__actions">
                  <Link to={`/body-progress/${session.id}`}>{t("bodyPhotos.results.viewAnalysis")}</Link>
                  <button type="button" onClick={(event) => openDeleteDialog(session, event.currentTarget)}>
                    {t("bodyPhotos.deleteDialog.deleteAnalysis")}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {deleteTarget !== null && (
        <div
          className="body-analysis-delete-overlay"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeDeleteDialog();
          }}
        >
          <section
            aria-describedby="body-analysis-delete-description"
            aria-labelledby="body-analysis-delete-title"
            aria-modal="true"
            className="body-analysis-delete-dialog"
            role="dialog"
          >
            <span className="body-analysis-delete-dialog__rail" aria-hidden="true" />
            <header>
              <span className="body-analysis-delete-dialog__icon" aria-hidden="true"><TrashIcon /></span>
              <div>
                <p>{t("bodyPhotos.deleteDialog.eyebrow")}</p>
                <h2 id="body-analysis-delete-title">
                  {t(deleteTarget.submitted_at === null
                    ? "bodyPhotos.deleteDialog.uploadTitle"
                    : "bodyPhotos.deleteDialog.analysisTitle")}
                </h2>
              </div>
            </header>
            <p id="body-analysis-delete-description" className="body-analysis-delete-dialog__description">
              {t(deleteTarget.submitted_at === null
                ? "bodyPhotos.deleteDialog.uploadBody"
                : "bodyPhotos.deleteDialog.analysisBody")}
            </p>
            <dl>
              <div>
                <dt>{t("bodyPhotos.deleteDialog.dateLabel")}</dt>
                <dd>{new Intl.DateTimeFormat(locale).format(new Date(deleteTarget.created_at))}</dd>
              </div>
              <div>
                <dt>{t("bodyPhotos.deleteDialog.statusLabel")}</dt>
                <dd>{t(`bodyPhotos.status.${deleteTarget.state}`)}</dd>
              </div>
            </dl>
            {deleteFailed && (
              <p className="form-error body-analysis-delete-dialog__error" role="alert">
                {t("bodyPhotos.deleteDialog.error")}
              </p>
            )}
            <footer>
              <button
                autoFocus
                className="body-analysis-delete-dialog__cancel"
                type="button"
                disabled={deletingSessionId !== null}
                onClick={closeDeleteDialog}
              >
                {t("bodyPhotos.deleteDialog.cancel")}
              </button>
              <button
                className="body-analysis-delete-dialog__confirm"
                type="button"
                disabled={deletingSessionId !== null}
                onClick={() => void removeSession()}
              >
                {deletingSessionId !== null
                  ? t("bodyPhotos.deleteDialog.deleting")
                  : t("bodyPhotos.deleteDialog.confirm")}
              </button>
            </footer>
          </section>
        </div>
      )}
    </main>
  );
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5" />
    </svg>
  );
}
