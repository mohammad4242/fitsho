import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { AppIcon } from "../../shared/AppIcon";
import { deleteBodyPhotoSession, getBodyProgressTimeline } from "./api";
import { BodyTimeline } from "./BodyTimeline";
import type { BodyProgressTimelineItem, BodyProgressTimelineResponse } from "./types";
import "./bodyPhotos.css";

export function BodyProgressPage() {
  const { t, i18n } = useTranslation();
  const [timeline, setTimeline] = useState<BodyProgressTimelineResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<BodyProgressTimelineItem["session"] | null>(null);
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null);
  const [deleteFailed, setDeleteFailed] = useState(false);
  const deleteTriggerRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    void getBodyProgressTimeline()
      .then((response) => setTimeline(response))
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

  const locale = i18n.resolvedLanguage === "en" ? "en" : "fa-IR";

  function openDeleteDialog(session: BodyProgressTimelineItem["session"], trigger: HTMLButtonElement) {
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
      setTimeline((current) => current === null
        ? current
        : { ...current, items: current.items.filter((item) => item.session.id !== sessionId) });
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

      {timeline === null && !failed && (
        <p className="body-analysis-home__status" role="status">{t("bodyPhotos.loading")}</p>
      )}
      {failed && <p className="form-error body-analysis-home__status" role="alert">{t("bodyPhotos.errors.load")}</p>}

      {timeline?.items.length === 0 && (
        <section className="body-analysis-empty" aria-labelledby="body-analysis-empty-title">
          <span className="body-analysis-empty__icon" aria-hidden="true"><AppIcon name="camera" /></span>
          <h2 id="body-analysis-empty-title">{t("bodyPhotos.emptyTitle")}</h2>
          <p>{t("bodyPhotos.emptyBody")}</p>
          <Link className="primary-button" to="/body-progress/new">{t("bodyPhotos.emptyAction")}</Link>
        </section>
      )}

      {timeline !== null && timeline.items.length > 0 && (
        <>
          <Link className="primary-button body-analysis-home__start" to="/body-progress/new">{t("bodyPhotos.start")}</Link>
          <BodyTimeline items={timeline.items} onDelete={openDeleteDialog} />
        </>
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
