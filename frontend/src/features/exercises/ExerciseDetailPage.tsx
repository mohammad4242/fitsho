import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useParams } from "react-router-dom";

import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { getExercise } from "./api";
import { ExerciseMedia } from "./ExerciseMedia";
import type { ExerciseDetail } from "./types";
import "./exercises.css";

type DetailState = "loading" | "ready" | "not-found" | "error";

export function ExerciseDetailPage() {
  const { i18n, t } = useTranslation();
  const { slug } = useParams();
  const location = useLocation();
  const [exercise, setExercise] = useState<ExerciseDetail | null>(null);
  const [state, setState] = useState<DetailState>("loading");
  const [retry, setRetry] = useState(0);
  const isEnglish = i18n.resolvedLanguage === "en";
  const catalogPath = `/exercises${location.search}`;

  useEffect(() => {
    if (slug === undefined) {
      setState("not-found");
      return;
    }

    let active = true;
    setState("loading");
    void getExercise(slug)
      .then((response) => {
        if (!active) return;
        if (response === null) {
          setExercise(null);
          setState("not-found");
          return;
        }
        setExercise(response);
        setState("ready");
      })
      .catch(() => {
        if (!active) return;
        setState("error");
      });
    return () => {
      active = false;
    };
  }, [retry, slug]);

  return (
    <div className="exercise-catalog-shell exercise-detail-shell">
      <AuthenticatedHeader />
      <main className="exercise-detail-main">
        {state === "loading" && (
          <DetailMessage role="status" message={t("exerciseDetail.loading")} />
        )}
        {state === "error" && (
          <DetailMessage
            role="alert"
            message={t("exerciseDetail.loadError")}
            action={t("common.retry")}
            onAction={() => setRetry((value) => value + 1)}
          />
        )}
        {state === "not-found" && (
          <section className="exercise-detail-message" aria-labelledby="unknown-exercise">
            <span className="exercise-detail-message__mark" aria-hidden="true">?</span>
            <h1 id="unknown-exercise">{t("exerciseDetail.unknownTitle")}</h1>
            <p>{t("exerciseDetail.unknownBody")}</p>
            <Link className="exercise-detail-back" to={catalogPath}>
              {t("exerciseDetail.backToCatalog")}
            </Link>
          </section>
        )}
        {state === "ready" && exercise !== null && (
          <ReadyExerciseDetail
            exercise={exercise}
            catalogPath={catalogPath}
            isEnglish={isEnglish}
          />
        )}
      </main>
    </div>
  );
}

function ReadyExerciseDetail({
  exercise,
  catalogPath,
  isEnglish,
}: {
  exercise: ExerciseDetail;
  catalogPath: string;
  isEnglish: boolean;
}) {
  const { t } = useTranslation();
  const name = isEnglish ? exercise.name_en : exercise.name_fa;
  const secondaryName = isEnglish ? exercise.name_fa : exercise.name_en;
  const instructions = isEnglish ? exercise.instructions_en : exercise.instructions_fa;
  const safetyNotes = isEnglish ? exercise.safety_notes_en : exercise.safety_notes_fa;
  const secondaryMuscles = exercise.secondary_muscles.map((value) =>
    t(`catalog.muscle.${value}`),
  );
  const equipmentNames = exercise.equipment.map((value) =>
    t(`catalog.equipment.${value}`),
  );

  return (
    <>
      <nav className="catalog-breadcrumb" aria-label={t("exerciseDetail.breadcrumbLabel")}>
        <Link to={catalogPath}>{t("catalog.title")}</Link>
        <span aria-hidden="true">←</span>
        <span>{t(`catalog.bodyRegion.${exercise.body_region}`)}</span>
        <span aria-hidden="true">←</span>
        <span>{t(`catalog.muscle.${exercise.primary_muscle}`)}</span>
        <span aria-hidden="true">←</span>
        <span aria-current="page">{name}</span>
      </nav>

      <article className="exercise-detail-sheet">
        <div className="exercise-detail-media">
          <ExerciseMedia path={exercise.media_path} name={name} mediaType={exercise.media_type} />
          {exercise.media_attribution !== null && (
            <small>{exercise.media_attribution}</small>
          )}
        </div>

        <header className="exercise-detail-heading">
          <p className="eyebrow eyebrow--accent">{t("exerciseDetail.eyebrow")}</p>
          <h1 dir={isEnglish ? "ltr" : "rtl"}>{name}</h1>
          <p className="exercise-detail-heading__secondary" dir={isEnglish ? "rtl" : "ltr"}>
            {secondaryName}
          </p>
          <dl className="exercise-detail-facts">
            <div>
              <dt>{t("exerciseDetail.bodyRegion")}</dt>
              <dd>{t(`catalog.bodyRegion.${exercise.body_region}`)}</dd>
            </div>
            <div>
              <dt>{t("catalog.primaryMuscleLabel")}</dt>
              <dd>{t(`catalog.muscle.${exercise.primary_muscle}`)}</dd>
            </div>
            <div>
              <dt>{t("exerciseDetail.secondaryMuscles")}</dt>
              <dd>
                {secondaryMuscles.length > 0
                  ? secondaryMuscles.join(t("catalog.listSeparator"))
                  : t("exerciseDetail.none")}
              </dd>
            </div>
            <div>
              <dt>{t("catalog.equipmentLabel")}</dt>
              <dd>{equipmentNames.join(t("catalog.listSeparator"))}</dd>
            </div>
            <div>
              <dt>{t("catalog.difficultyLabel")}</dt>
              <dd>{t(`catalog.difficulty.${exercise.difficulty}`)}</dd>
            </div>
          </dl>
        </header>

        <section className="exercise-instructions" aria-labelledby="instructions-heading">
          <div className="exercise-detail-section-heading">
            <span aria-hidden="true">✓</span>
            <h2 id="instructions-heading">{t("exerciseDetail.instructionsTitle")}</h2>
          </div>
          <ol>
            {instructions.map((instruction) => (
              <li key={instruction}>{instruction}</li>
            ))}
          </ol>
        </section>

        <section className="exercise-safety" aria-labelledby="safety-heading">
          <div className="exercise-detail-section-heading">
            <span aria-hidden="true">!</span>
            <h2 id="safety-heading">{t("exerciseDetail.safetyTitle")}</h2>
          </div>
          <ul>
            {safetyNotes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>

        <Link className="exercise-detail-back" to={catalogPath}>
          {t("exerciseDetail.backToCatalog")}
          <span aria-hidden="true">←</span>
        </Link>
      </article>
    </>
  );
}

function DetailMessage({
  role,
  message,
  action,
  onAction,
}: {
  role: "status" | "alert";
  message: string;
  action?: string;
  onAction?: () => void;
}) {
  return (
    <div className="catalog-status exercise-detail-status" role={role}>
      <span className="catalog-status__mark" aria-hidden="true" />
      <p>{message}</p>
      {action !== undefined && onAction !== undefined && (
        <button className="retry-button" type="button" onClick={onAction}>
          {action}
        </button>
      )}
    </div>
  );
}
