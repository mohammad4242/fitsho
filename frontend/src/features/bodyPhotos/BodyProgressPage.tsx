import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { getBodyPhotoSessions } from "./api";
import type { BodyPhotoSession } from "./types";
import "./bodyPhotos.css";

export function BodyProgressPage() {
  const { t } = useTranslation();
  const [sessions, setSessions] = useState<BodyPhotoSession[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    void getBodyPhotoSessions()
      .then((response) => setSessions(response.items))
      .catch(() => setFailed(true));
  }, []);

  return <main className="body-progress-page">
    <header><p className="eyebrow eyebrow--accent">{t("bodyPhotos.eyebrow")}</p><h1 className="fitsho-display">{t("bodyPhotos.progressTitle")}</h1><p>{t("bodyPhotos.optionalIntro")}</p></header>
    <Link className="primary-button" to="/body-progress/new">{t("bodyPhotos.start")}</Link>
    {sessions === null && !failed && <p role="status">{t("bodyPhotos.loading")}</p>}
    {failed && <p className="form-error" role="alert">{t("bodyPhotos.errors.load")}</p>}
    {sessions?.length === 0 && <p>{t("bodyPhotos.empty")}</p>}
    <ul className="body-progress-list">
      {sessions?.map((session) => <li key={session.id}><strong>{new Intl.DateTimeFormat().format(new Date(session.created_at))}</strong><span>{t(`bodyPhotos.status.${session.state}`)}</span><span>{session.photos.length}/3</span></li>)}
    </ul>
  </main>;
}
