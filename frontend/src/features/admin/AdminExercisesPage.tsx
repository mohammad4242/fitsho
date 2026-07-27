import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router-dom";

import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { getAdminExercises } from "./api";
import type { PaginatedAdminExercises } from "./types";
import "./admin.css";

export function AdminExercisesPage() {
  const { i18n, t } = useTranslation();
  const location = useLocation();
  const [page, setPage] = useState<PaginatedAdminExercises | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [retry, setRetry] = useState(0);
  const createdId = (location.state as { createdId?: string } | null)?.createdId;
  const createdExerciseRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    let active = true;
    setState("loading");
    void getAdminExercises({ page_size: 100 })
      .then((result) => {
        if (!active) return;
        setPage(result);
        setState("ready");
      })
      .catch(() => {
        if (active) setState("error");
      });
    return () => { active = false; };
  }, [retry]);

  useEffect(() => {
    if (state === "ready" && createdId) createdExerciseRef.current?.focus();
  }, [createdId, state]);

  const english = i18n.resolvedLanguage === "en";
  return (
    <div className="admin-page">
      <AuthenticatedHeader />
      <main className="admin-main">
        <header className="admin-hero">
          <div>
            <p className="eyebrow eyebrow--accent">{t("admin.exercises.eyebrow")}</p>
            <h1>{t("admin.exercises.title")}</h1>
            <p>{t("admin.exercises.intro")}</p>
          </div>
          <Link className="admin-primary-link" to="/admin/exercises/new">
            {t("admin.exercises.add")}
          </Link>
        </header>

        {state === "loading" && <p className="admin-status" role="status">{t("admin.exercises.loading")}</p>}
        {state === "error" && (
          <div className="admin-status" role="alert">
            <p>{t("admin.exercises.loadError")}</p>
            <button type="button" onClick={() => setRetry((value) => value + 1)}>{t("common.retry")}</button>
          </div>
        )}
        {state === "ready" && page?.items.length === 0 && (
          <p className="admin-status">{t("admin.exercises.empty")}</p>
        )}
        {state === "ready" && createdId && (
          <div className="admin-status admin-status--success" role="status">
            <p>{t("admin.exercises.created")}</p>
            <a href={`#exercise-${createdId}`}>{t("admin.exercises.viewCreated")}</a>
          </div>
        )}
        {state === "ready" && page && page.items.length > 0 && (
          <section className="admin-exercise-list" aria-label={t("admin.exercises.listLabel")}>
            {page.items.map((exercise) => (
              <article
                className={`admin-exercise-row${exercise.id === createdId ? " is-created" : ""}`}
                id={`exercise-${exercise.id}`}
                key={exercise.id}
                ref={exercise.id === createdId ? createdExerciseRef : undefined}
                tabIndex={exercise.id === createdId ? -1 : undefined}
              >
                <span className={`admin-state admin-state--${exercise.is_active ? "active" : "inactive"}`}>
                  {t(`admin.exercises.${exercise.is_active ? "active" : "inactive"}`)}
                </span>
                <div>
                  <h2>{english ? exercise.name_en : exercise.name_fa}</h2>
                  <p dir="ltr">{exercise.slug}</p>
                </div>
                <dl>
                  <div><dt>{t("catalog.primaryMuscleLabel")}</dt><dd>{t(`catalog.muscle.${exercise.primary_muscle}`)}</dd></div>
                  <div><dt>{t("catalog.difficultyLabel")}</dt><dd>{t(`catalog.difficulty.${exercise.difficulty}`)}</dd></div>
                </dl>
              </article>
            ))}
          </section>
        )}
      </main>
    </div>
  );
}
