import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

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

  return <main className="body-progress-page fitsho-page">
    <header><div><p className="eyebrow eyebrow--accent">{t("bodyPhotos.eyebrow")}</p><h1 className="fitsho-display">{t("bodyPhotos.progressTitle")}</h1></div><Link className="primary-button" to="/body-progress/new">{t("bodyPhotos.start")}</Link><p>{t("bodyPhotos.optionalIntro")}</p></header>
    {sessions === null && !failed && <p role="status">{t("bodyPhotos.loading")}</p>}
    {failed && <p className="form-error" role="alert">{t("bodyPhotos.errors.load")}</p>}
    {sessions?.length === 0 && <p>{t("bodyPhotos.empty")}</p>}
    <ul className="body-progress-list" aria-label={t("bodyPhotos.progressTitle")}>
      {sessions?.map((session, index) => <li className={index === 0 ? "body-progress-list__latest" : undefined} key={session.id}>{index === 0 && session.photos[0] && <figure><img src={session.photos[0].content_url} alt={l("آخرین عکس پیشرفت", "Latest progress photo")} /></figure>}<div>{index === 0 && <small>{l("آخرین تحلیل", "Latest analysis")}</small>}<strong>{new Intl.DateTimeFormat().format(new Date(session.created_at))}</strong><span>{t(`bodyPhotos.status.${session.state}`)}</span></div><span>{session.photos.length}/3</span><Link to={`/body-progress/${session.id}`}>{t("bodyPhotos.results.viewAnalysis")}</Link></li>)}
    </ul>
  </main>;
}
