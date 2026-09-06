import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { AppIcon } from "../../shared/AppIcon";
import bodyAnalysisHeroImg from "../../assets/bodyPhotos/bodyanalysis.jpg";
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

  const isFa = !i18n.resolvedLanguage?.startsWith("en");

  return (
    <main className="body-analysis-home fitsho-page">
      <header className="body-analysis-home__header">
        <div className="body-analysis-home__badge">
          <span className="body-analysis-home__badge-dot" aria-hidden="true" />
          <span>{isFa ? "آنالیز هوشمند ترکیب و فرم بدن" : "AI Body Biometrics & Composition"}</span>
        </div>
        <h1 dir="ltr">Body Analysis</h1>
        <p className="body-analysis-home__subtitle">
          {isFa
            ? "پایش دقیق روند تغییرات فیزیکی، دورسنجی‌ها و ثبت بصری پیشرفت بدن"
            : "Track visual progress, body circumferences, and physical transformation over time"}
        </p>
        <p className="body-analysis-home__intro">{t("bodyPhotos.optionalIntro")}</p>

        <div className="body-analysis-home__features" aria-label={isFa ? "امکانات آنالیز بدن" : "Features"}>
          <div className="body-analysis-feature-chip">
            <span className="body-analysis-feature-chip__icon" aria-hidden="true">🔒</span>
            <div className="body-analysis-feature-chip__text">
              <strong>{isFa ? "حفظ ۱۰۰٪ حریم خصوصی" : "Privacy First"}</strong>
              <small>{isFa ? "برش خودکار چهره روی گوشی پیش از بارگذاری" : "On-device automatic face crop"}</small>
            </div>
          </div>
          <div className="body-analysis-feature-chip">
            <span className="body-analysis-feature-chip__icon" aria-hidden="true">📐</span>
            <div className="body-analysis-feature-chip__text">
              <strong>{isFa ? "راهنمای استاندارد Ghost" : "Ghost Alignment"}</strong>
              <small>{isFa ? "عکاسی دقیق در ۳ زاویه روبه‌رو، نیمرخ و پشت" : "Standardized 3-view body angles"}</small>
            </div>
          </div>
          <div className="body-analysis-feature-chip">
            <span className="body-analysis-feature-chip__icon" aria-hidden="true">📊</span>
            <div className="body-analysis-feature-chip__text">
              <strong>{isFa ? "دورسنجی و تحلیل روند" : "Biometric Tracking"}</strong>
              <small>{isFa ? "پایش دور کمر، باسن، شانه و اسلایدر قبل/بعد" : "Waist, hips, shoulders & before/after slider"}</small>
            </div>
          </div>
        </div>
      </header>

      {timeline === null && !failed && (
        <div className="body-analysis-home__status-box">
          <span className="body-analysis-home__status-spinner" aria-hidden="true" />
          <p className="body-analysis-home__status" role="status">{t("bodyPhotos.loading")}</p>
        </div>
      )}
      {failed && <p className="form-error body-analysis-home__status" role="alert">{t("bodyPhotos.errors.load")}</p>}

      {timeline?.items.length === 0 && (
        <section className="body-analysis-empty" aria-labelledby="body-analysis-empty-title">
          <div className="body-analysis-empty__visual">
            <div className="body-analysis-empty__media-frame">
              <img
                src={bodyAnalysisHeroImg}
                alt=""
                aria-hidden="true"
                className="body-analysis-empty__image"
              />
              <div className="body-analysis-empty__overlay">
                <span className="body-analysis-empty__corner body-analysis-empty__corner--tl" aria-hidden="true" />
                <span className="body-analysis-empty__corner body-analysis-empty__corner--tr" aria-hidden="true" />
                <span className="body-analysis-empty__corner body-analysis-empty__corner--bl" aria-hidden="true" />
                <span className="body-analysis-empty__corner body-analysis-empty__corner--br" aria-hidden="true" />
                <div className="body-analysis-empty__scan-line" aria-hidden="true" />
                <div className="body-analysis-empty__hud-badge">
                  <span className="body-analysis-empty__hud-dot" aria-hidden="true" />
                  <span>{isFa ? "اسکن هوشمند دوربین و بیومتریک بدن" : "Smart Camera & Body Biometric Scan"}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="body-analysis-empty__content">
            <h2 id="body-analysis-empty-title">{t("bodyPhotos.emptyTitle")}</h2>
            <p>{t("bodyPhotos.emptyBody")}</p>

            <div className="body-analysis-empty__steps" aria-label={isFa ? "مراحل ثبت" : "Steps"}>
              <div className="body-analysis-empty__step">
                <span className="body-analysis-empty__step-badge">۱</span>
                <div className="body-analysis-empty__step-info">
                  <strong>{isFa ? "عکاسی ۳ زاویه" : "3 Standard Angles"}</strong>
                  <small>{isFa ? "روبه‌رو، نیمرخ، پشت" : "Front, Side, Back"}</small>
                </div>
              </div>
              <div className="body-analysis-empty__step">
                <span className="body-analysis-empty__step-badge">۲</span>
                <div className="body-analysis-empty__step-info">
                  <strong>{isFa ? "برش امن چهره" : "Face-Safe Crop"}</strong>
                  <small>{isFa ? "کاملاً محرمانه در گوشی" : "100% On-device privacy"}</small>
                </div>
              </div>
              <div className="body-analysis-empty__step">
                <span className="body-analysis-empty__step-badge">۳</span>
                <div className="body-analysis-empty__step-info">
                  <strong>{isFa ? "تحلیل و دورسنجی" : "Biometric Report"}</strong>
                  <small>{isFa ? "نمودار و روند پیشرفت" : "Progress comparison"}</small>
                </div>
              </div>
            </div>

            <Link className="primary-button body-analysis-empty__action" to="/body-progress/new">
              <span className="body-analysis-empty__action-icon" aria-hidden="true">
                <AppIcon name="camera" />
              </span>
              <span>{t("bodyPhotos.emptyAction")}</span>
            </Link>
          </div>
        </section>
      )}

      {timeline !== null && timeline.items.length > 0 && (
        <div className="body-analysis-home__timeline-container">
          <div className="body-analysis-home__toolbar">
            <div className="body-analysis-home__toolbar-left">
              <div className="body-analysis-home__toolbar-media" aria-hidden="true">
                <img src={bodyAnalysisHeroImg} alt="" className="body-analysis-home__toolbar-thumb" />
                <span className="body-analysis-home__toolbar-scan-indicator" />
              </div>
              <div className="body-analysis-home__toolbar-info">
                <strong>{isFa ? "جلسه جدید آنالیز بدن" : "New Body Analysis Session"}</strong>
                <span className="body-analysis-stat-pill">
                  <span className="body-analysis-stat-pill__dot" aria-hidden="true" />
                  <span>
                    {isFa
                      ? `${timeline.items.length} جلسه تحلیل ثبت‌شده`
                      : `${timeline.items.length} total sessions`}
                  </span>
                </span>
              </div>
            </div>
            <Link className="primary-button body-analysis-home__start" to="/body-progress/new">
              <span className="body-analysis-home__start-icon" aria-hidden="true">
                <AppIcon name="camera" />
              </span>
              <span>{t("bodyPhotos.start")}</span>
            </Link>
          </div>
          <BodyTimeline items={timeline.items} onDelete={openDeleteDialog} />
        </div>
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
