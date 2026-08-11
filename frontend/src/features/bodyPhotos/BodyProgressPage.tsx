import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { AppIcon } from "../../shared/AppIcon";
import { getBodyPhotoSessions } from "./api";
import type { BodyPhotoSession } from "./types";
import "./bodyPhotos.css";

export function BodyProgressPage() {
  const { t, i18n } = useTranslation();
  const l = (fa: string, en: string) => i18n.resolvedLanguage === "en" ? en : fa;
  const [sessions, setSessions] = useState<BodyPhotoSession[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    void getBodyPhotoSessions()
      .then((response) => setSessions(response.items))
      .catch(() => setFailed(true));
  }, []);

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

      {sessions && sessions.length > 0 && (
        <section className="body-analysis-history" aria-labelledby="body-analysis-history-title">
          <header>
            <div>
              <p>{t("bodyPhotos.scannerLabel")}</p>
              <h2 id="body-analysis-history-title">{t("bodyPhotos.historyTitle")}</h2>
            </div>
            <Link className="primary-button" to="/body-progress/new">{t("bodyPhotos.start")}</Link>
          </header>
          <ul aria-label={t("bodyPhotos.progressTitle")}>
            {sessions.map((session, index) => (
              <li className={index === 0 ? "body-analysis-session body-analysis-session--latest" : "body-analysis-session"} key={session.id}>
                {index === 0 && session.photos[0] && (
                  <figure><img src={session.photos[0].content_url} alt={l("آخرین عکس تحلیل بدن", "Latest progress photo")} /></figure>
                )}
                <div>
                  {index === 0 && <small>{l("آخرین تحلیل", "Latest analysis")}</small>}
                  <strong>{new Intl.DateTimeFormat(i18n.resolvedLanguage === "en" ? "en" : "fa-IR").format(new Date(session.created_at))}</strong>
                  <span>{t(`bodyPhotos.status.${session.state}`)}</span>
                </div>
                <span>{session.photos.length}/3</span>
                <Link to={`/body-progress/${session.id}`}>{t("bodyPhotos.results.viewAnalysis")}</Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
