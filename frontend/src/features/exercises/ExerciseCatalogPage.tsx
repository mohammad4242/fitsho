import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";

import heroStrengthFallback from "../../assets/landing/hero-strength-fallback.jpg";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import { deleteAdminExercise, getAdminExercises } from "../admin/api";
import { useAuth } from "../auth/AuthContext";
import { getExerciseCategories, getExercises } from "./api";
import { ExerciseMedia } from "./ExerciseMedia";
import {
  bodyRegions,
  difficulties,
  equipment,
  muscleFocuses,
  muscleGroups,
  type BodyRegion,
  type Difficulty,
  type Equipment,
  type ExerciseCategories,
  type ExerciseCategory,
  type ExerciseFilters,
  type ExerciseLabel,
  type MuscleFocus,
  type MuscleFocusCategory,
  type ExerciseSummary,
  type ExerciseType,
  type MuscleGroup,
  type PaginatedExercises,
} from "./types";
import "./exercises.css";

type LoadState = "idle" | "loading" | "ready" | "error";

type CatalogQuery = {
  body_region?: BodyRegion;
  primary_muscle?: MuscleGroup;
  muscle_focus?: MuscleFocus;
  equipment?: Equipment;
  difficulty?: Difficulty;
  exercise_type?: ExerciseType;
  labels?: ExerciseLabel[];
  search?: string;
  admin_status?: AdminStatus;
  page: number;
};

type AdminStatus = "all" | "inactive" | "needs_review";
type CatalogExercise = ExerciseSummary & { is_active?: boolean; needs_review?: boolean };

export function ExerciseCatalogPage() {
  const { i18n, t } = useTranslation();
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [categories, setCategories] = useState<ExerciseCategories | null>(null);
  const [categoryState, setCategoryState] = useState<LoadState>("loading");
  const [categoryRetry, setCategoryRetry] = useState(0);
  const [exercisePage, setExercisePage] = useState<PaginatedExercises | null>(null);
  const [exerciseState, setExerciseState] = useState<LoadState>("idle");
  const [exerciseRetry, setExerciseRetry] = useState(0);
  const [deleteTarget, setDeleteTarget] = useState<CatalogExercise | null>(null);
  const [deletingExerciseId, setDeletingExerciseId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const deleteTriggerRef = useRef<HTMLButtonElement | null>(null);

  const query = useMemo(() => parseCatalogQuery(searchParams), [searchParams]);
  const isEnglish = i18n.resolvedLanguage === "en";
  const regionCategory = categories?.body_regions.find(
    (category) => category.value === query.body_region,
  );
  const availableMuscles =
    categories !== null && query.body_region !== undefined
      ? categories[query.body_region]
      : [];
  const muscleCategory = availableMuscles.find(
    (category) => category.value === query.primary_muscle,
  );
  const selectedMuscle = muscleCategory?.value;
  const availableFocuses = selectedMuscle === undefined || categories === null
    ? []
    : categories.muscle_focuses[selectedMuscle];
  const focusCategory = availableFocuses.find(
    (category) => category.value === query.muscle_focus,
  );
  const selectedFocus = focusCategory?.value;
  const selectedLabel = query.labels?.[0];
  const hasSpecialFilter = selectedLabel !== undefined || query.exercise_type === "mobility";
  const isAdmin = user?.is_admin === true;
  const adminStatus = isAdmin ? query.admin_status : undefined;
  const canLoadExercises = adminStatus !== undefined || hasSpecialFilter || (regionCategory !== undefined && selectedMuscle !== undefined);

  useEffect(() => {
    let active = true;
    setCategoryState("loading");
    void getExerciseCategories()
      .then((response) => {
        if (!active) return;
        setCategories(response);
        setCategoryState("ready");
      })
      .catch(() => {
        if (!active) return;
        setCategoryState("error");
      });
    return () => {
      active = false;
    };
  }, [categoryRetry]);

  useEffect(() => {
    if (!canLoadExercises) {
      setExercisePage(null);
      setExerciseState("idle");
      return;
    }

    let active = true;
    setExerciseState("loading");
    const filters: ExerciseFilters = {
      body_region: query.body_region,
      primary_muscle: selectedMuscle,
      muscle_focus: selectedFocus,
      equipment: query.equipment,
      difficulty: query.difficulty,
      exercise_type: query.exercise_type,
      labels: query.labels,
      search: query.search?.trim() || undefined,
      page: query.page,
    };
    const request = adminStatus === undefined
      ? getExercises(filters)
      : getAdminExercises({
          ...filters,
          is_active: adminStatus === "inactive" ? false : undefined,
          needs_review: adminStatus === "needs_review" ? true : undefined,
        });
    void request
      .then((response) => {
        if (!active) return;
        setExercisePage(response);
        setExerciseState("ready");
      })
      .catch(() => {
        if (!active) return;
        setExerciseState("error");
      });
    return () => {
      active = false;
    };
  }, [
    exerciseRetry,
    adminStatus,
    canLoadExercises,
    query.body_region,
    query.difficulty,
    query.exercise_type,
    query.equipment,
    query.labels,
    query.page,
    query.search,
    selectedFocus,
    selectedMuscle,
  ]);

  useEffect(() => {
    if (deleteTarget === null) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape" || deletingExerciseId !== null) return;
      event.preventDefault();
      setDeleteTarget(null);
      setDeleteError(null);
      deleteTriggerRef.current?.focus();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [deleteTarget, deletingExerciseId]);

  function writeQuery(
    changes: Partial<Omit<CatalogQuery, "page">> & { page?: number },
    resetPage = true,
  ) {
    const next = { ...query, ...changes };
    if (resetPage) next.page = 1;
    setSearchParams(serializeCatalogQuery(next));
  }

  function chooseRegion(value: BodyRegion) {
    writeQuery({ body_region: value, primary_muscle: undefined, muscle_focus: undefined, labels: undefined, exercise_type: undefined });
  }

  function chooseMuscle(value: MuscleGroup) {
    writeQuery({ primary_muscle: value, muscle_focus: undefined, labels: undefined, exercise_type: undefined });
  }

  function chooseFocus(value: MuscleFocus | undefined) {
    writeQuery({ muscle_focus: value });
  }

  function chooseSpecialFilter(changes: Pick<CatalogQuery, "labels" | "exercise_type">) {
    writeQuery({ ...changes, body_region: undefined, primary_muscle: undefined, muscle_focus: undefined });
  }

  function resetLibrary() {
    setSearchParams(new URLSearchParams());
  }

  function resetToRegion() {
    writeQuery({ primary_muscle: undefined, muscle_focus: undefined });
  }

  function openDeleteDialog(exercise: CatalogExercise, trigger: HTMLButtonElement) {
    deleteTriggerRef.current = trigger;
    setDeleteError(null);
    setDeleteTarget(exercise);
  }

  function closeDeleteDialog() {
    if (deletingExerciseId !== null) return;
    setDeleteTarget(null);
    setDeleteError(null);
    deleteTriggerRef.current?.focus();
  }

  async function handleDelete() {
    if (deleteTarget === null) return;
    const exercise = deleteTarget;
    setDeletingExerciseId(exercise.id);
    setDeleteError(null);
    try {
      await deleteAdminExercise(exercise.id);
      setExercisePage((current) => current === null
        ? current
        : {
            ...current,
            items: current.items.filter((item) => item.id !== exercise.id),
            total: Math.max(0, current.total - 1),
          });
      setDeleteTarget(null);
    } catch {
      setDeleteError(t("catalog.deleteExerciseError"));
    } finally {
      setDeletingExerciseId(null);
    }
  }

  const hasResultFilters = Boolean(selectedFocus || query.equipment || query.difficulty || query.search?.trim());
  const currentSearch = searchParams.toString();
  const returnTo = `/exercises${currentSearch ? `?${currentSearch}` : ""}`;
  const createParams = new URLSearchParams();
  if (query.body_region !== undefined) createParams.set("body_region", query.body_region);
  if (query.primary_muscle !== undefined) createParams.set("primary_muscle", query.primary_muscle);
  if (selectedFocus !== undefined) createParams.set("muscle_focus", selectedFocus);
  createParams.set("return_to", returnTo);

  return (
    <div className="exercise-catalog-shell">
      <MemberHeaderMedia imageSrc={heroStrengthFallback} className="member-page-background" />
      <main className="exercise-catalog-main">
        <header className="exercise-catalog-hero">
          <div>
            <p className="eyebrow eyebrow--accent">{t("catalog.eyebrow")}</p>
            <h1 className="fitsho-display">{t("catalog.title")}</h1>
          </div>
          <p>{t("catalog.intro")}</p>
        </header>

        <CatalogBreadcrumb
          region={regionCategory}
          muscle={muscleCategory}
          focus={focusCategory}
          isEnglish={isEnglish}
          onLibrary={resetLibrary}
          onRegion={resetToRegion}
          onMuscle={() => chooseFocus(undefined)}
        />

        {isAdmin && (
          <section className="catalog-admin-toolbar" aria-label={t("catalog.adminTools")}>
            <Link className="catalog-admin-add" to={`/admin/exercises/new?${createParams.toString()}`}>
              {t("catalog.addExercise")}
            </Link>
            <label>
              <span>{t("catalog.adminStatusLabel")}</span>
              <select
                value={adminStatus ?? "published"}
                onChange={(event) => writeQuery({
                  admin_status: optionalValue(event.currentTarget.value, ["all", "inactive", "needs_review"] as const),
                })}
              >
                <option value="published">{t("catalog.adminStatus.published")}</option>
                <option value="all">{t("catalog.adminStatus.all")}</option>
                <option value="inactive">{t("catalog.adminStatus.inactive")}</option>
                <option value="needs_review">{t("catalog.adminStatus.needs_review")}</option>
              </select>
            </label>
          </section>
        )}

        <section className="catalog-special-filters" aria-label={t("catalog.specialFiltersTitle")}>
          <p>{t("catalog.specialFiltersTitle")}</p>
          <div>
            <button
              className={selectedLabel === "full_body" ? "is-active" : ""}
              type="button"
              aria-pressed={selectedLabel === "full_body"}
              onClick={() => chooseSpecialFilter({ labels: ["full_body"], exercise_type: undefined })}
            >
              {t("catalog.label.full_body")}
            </button>
            <button
              className={selectedLabel === "cardio" ? "is-active" : ""}
              type="button"
              aria-pressed={selectedLabel === "cardio"}
              onClick={() => chooseSpecialFilter({ labels: ["cardio"], exercise_type: undefined })}
            >
              {t("catalog.label.cardio")}
            </button>
            <button
              className={query.exercise_type === "mobility" ? "is-active" : ""}
              type="button"
              aria-pressed={query.exercise_type === "mobility"}
              onClick={() => chooseSpecialFilter({ labels: undefined, exercise_type: "mobility" })}
            >
              {t("catalog.mobility")}
            </button>
          </div>
        </section>

        {categoryState === "loading" && (
          <StatusPanel role="status" message={t("catalog.loadingCategories")} />
        )}
        {categoryState === "error" && (
          <StatusPanel
            role="alert"
            message={t("catalog.categoryError")}
            action={t("common.retry")}
            onAction={() => setCategoryRetry((value) => value + 1)}
          />
        )}

        {categories !== null && categoryState === "ready" && (
          <>
            <section className="catalog-stage" aria-labelledby="region-heading">
              <div className="catalog-stage__heading">
                <span>01</span>
                <div>
                  <h2 id="region-heading" className="fitsho-display">{t("catalog.regionTitle")}</h2>
                  <p>{t("catalog.regionIntro")}</p>
                </div>
              </div>
              <div className="region-selector" role="group" aria-label={t("catalog.regionTitle")}>
                {categories.body_regions.map((category) => (
                  <CategoryButton
                    key={category.value}
                    category={category}
                    active={category.value === query.body_region}
                    isEnglish={isEnglish}
                    onClick={() => chooseRegion(category.value)}
                    kind="region"
                  />
                ))}
              </div>
            </section>

            {regionCategory !== undefined && (
              <section className="catalog-stage" aria-labelledby="muscle-heading">
                <div className="catalog-stage__heading">
                  <span>02</span>
                  <div>
                  <h2 id="muscle-heading" className="fitsho-display">{t("catalog.muscleTitle")}</h2>
                    <p>{t("catalog.muscleIntro", { region: activeName(regionCategory, isEnglish) })}</p>
                  </div>
                </div>
                <div className="muscle-selector" role="group" aria-label={t("catalog.muscleTitle")}>
                  {availableMuscles.map((category) => (
                    <CategoryButton
                      key={category.value}
                      category={category}
                      active={category.value === selectedMuscle}
                      isEnglish={isEnglish}
                      onClick={() => chooseMuscle(category.value)}
                      kind="muscle"
                      compact={category.value === "forearms" || category.value === "neck"}
                    />
                  ))}
                </div>
              </section>
            )}

            {muscleCategory !== undefined && (
              <section className="catalog-stage catalog-stage--focus" aria-labelledby="focus-heading">
                <div className="catalog-stage__heading">
                  <span>03</span>
                  <div>
                    <h2 id="focus-heading" className="fitsho-display">{t("catalog.focusTitle")}</h2>
                    <p>{t("catalog.focusIntro", { muscle: activeName(muscleCategory, isEnglish) })}</p>
                  </div>
                </div>
                <div className="focus-selector" role="group" aria-label={t("catalog.focusTitle")}>
                  <button
                    className={`focus-button${selectedFocus === undefined ? " is-active" : ""}`}
                    type="button"
                    aria-pressed={selectedFocus === undefined}
                    onClick={() => chooseFocus(undefined)}
                  >
                    {t("catalog.allMuscleFocuses", { muscle: activeName(muscleCategory, isEnglish) })}
                  </button>
                  {availableFocuses.map((category) => (
                    <CategoryButton
                      key={category.value}
                      category={category}
                      active={category.value === selectedFocus}
                      isEnglish={isEnglish}
                      onClick={() => chooseFocus(category.value)}
                      kind="focus"
                    />
                  ))}
                </div>
              </section>
            )}
          </>
        )}

        {canLoadExercises && (
          <section className="catalog-results" aria-labelledby="results-heading">
            <div className="catalog-stage__heading catalog-stage__heading--results">
              <span>04</span>
              <div>
                <h2 id="results-heading" className="fitsho-display">
                  {resultHeading(query, muscleCategory, focusCategory, isEnglish, t)}
                </h2>
                <p>{t("catalog.resultsIntro")}</p>
              </div>
            </div>

            <div className="exercise-filters" aria-label={t("catalog.filtersTitle")}>
              <label>
                <span>{t("catalog.equipmentLabel")}</span>
                <select
                  value={query.equipment ?? ""}
                  onChange={(event) =>
                    writeQuery({ equipment: optionalValue(event.currentTarget.value, equipment) })
                  }
                >
                  <option value="">{t("catalog.allEquipment")}</option>
                  {equipment.map((value) => (
                    <option key={value} value={value}>
                      {t(`catalog.equipment.${value}`)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>{t("catalog.difficultyLabel")}</span>
                <select
                  value={query.difficulty ?? ""}
                  onChange={(event) =>
                    writeQuery({
                      difficulty: optionalValue(event.currentTarget.value, difficulties),
                    })
                  }
                >
                  <option value="">{t("catalog.allDifficulties")}</option>
                  {difficulties.map((value) => (
                    <option key={value} value={value}>
                      {t(`catalog.difficulty.${value}`)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="exercise-filter-search">
                <span>{t("catalog.searchLabel")}</span>
                <input
                  type="search"
                  value={query.search ?? ""}
                  placeholder={t("catalog.searchPlaceholder")}
                  onChange={(event) => writeQuery({ search: event.currentTarget.value || undefined })}
                />
              </label>
            </div>

            {exerciseState === "loading" && (
              <StatusPanel role="status" message={t("catalog.loadingExercises")} compact />
            )}
            {exerciseState === "error" && (
              <StatusPanel
                role="alert"
                message={t("catalog.exerciseError")}
                action={t("common.retry")}
                onAction={() => setExerciseRetry((value) => value + 1)}
                compact
              />
            )}
            {exerciseState === "ready" && exercisePage?.items.length === 0 && (
              <StatusPanel
                role="status"
                message={hasResultFilters ? t("catalog.noMatches") : t("catalog.emptyGroup")}
                compact
              />
            )}
            {exerciseState === "ready" &&
              exercisePage !== null &&
              categories !== null &&
              exercisePage.items.length > 0 && (
              <>
                <div className="exercise-card-grid">
                  {exercisePage.items.map((exercise) => (
                    <ExerciseCard
                      key={exercise.id}
                      exercise={exercise}
                      categories={categories}
                      isEnglish={isEnglish}
                      catalogSearch={currentSearch}
                      isAdmin={isAdmin}
                      returnTo={returnTo}
                      onDelete={openDeleteDialog}
                    />
                  ))}
                </div>
                {exercisePage.total_pages > 1 && (
                  <nav className="catalog-pagination" aria-label={t("catalog.paginationLabel")}>
                    <button
                      type="button"
                      disabled={query.page <= 1}
                      onClick={() => writeQuery({ page: query.page - 1 }, false)}
                    >
                      {t("catalog.previousPage")}
                    </button>
                    <span>
                      {t("catalog.pageCount", {
                        current: query.page,
                        total: exercisePage.total_pages,
                      })}
                    </span>
                    <button
                      type="button"
                      disabled={query.page >= exercisePage.total_pages}
                      onClick={() => writeQuery({ page: query.page + 1 }, false)}
                    >
                      {t("catalog.nextPage")}
                    </button>
                  </nav>
                )}
              </>
            )}
          </section>
        )}
      </main>
      {deleteTarget !== null && (
        <div
          className="exercise-delete-overlay"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeDeleteDialog();
          }}
        >
          <section
            aria-describedby="exercise-delete-description"
            aria-label={t("catalog.deleteDialogLabel")}
            aria-modal="true"
            className="exercise-delete-dialog"
            role="dialog"
          >
            <span className="exercise-delete-dialog__rail" aria-hidden="true" />
            <header>
              <span className="exercise-delete-dialog__icon" aria-hidden="true"><TrashIcon /></span>
              <div>
                <p>{t("catalog.deleteEyebrow")}</p>
                <h2>{t("catalog.deleteDialogTitle")}</h2>
              </div>
            </header>
            <p id="exercise-delete-description" className="exercise-delete-dialog__description">
              {t("catalog.deleteDialogBody", {
                name: isEnglish ? deleteTarget.name_en : deleteTarget.name_fa,
              })}
            </p>
            {deleteError !== null && (
              <p className="exercise-delete-dialog__error" role="alert">{deleteError}</p>
            )}
            <footer>
              <button
                autoFocus
                className="exercise-delete-dialog__cancel"
                type="button"
                disabled={deletingExerciseId !== null}
                onClick={closeDeleteDialog}
              >
                {t("catalog.deleteCancel")}
              </button>
              <button
                className="exercise-delete-dialog__confirm"
                type="button"
                disabled={deletingExerciseId !== null}
                onClick={() => void handleDelete()}
              >
                {deletingExerciseId !== null
                  ? t("catalog.deleteBusy")
                  : t("catalog.deleteConfirm")}
              </button>
            </footer>
          </section>
        </div>
      )}
    </div>
  );
}

function CatalogBreadcrumb({
  region,
  muscle,
  focus,
  isEnglish,
  onLibrary,
  onRegion,
  onMuscle,
}: {
  region?: { name_en: string; name_fa: string };
  muscle?: ExerciseCategory;
  focus?: MuscleFocusCategory;
  isEnglish: boolean;
  onLibrary: () => void;
  onRegion: () => void;
  onMuscle: () => void;
}) {
  const { t } = useTranslation();
  return (
    <nav className="catalog-breadcrumb" aria-label={t("catalog.breadcrumbLabel")}>
      <button type="button" onClick={onLibrary}>
        {t("catalog.title")}
      </button>
      {region !== undefined && (
        <>
          <span aria-hidden="true">←</span>
          <button type="button" onClick={onRegion}>
            {activeName(region, isEnglish)}
          </button>
        </>
      )}
      {muscle !== undefined && (
        <>
          <span aria-hidden="true">←</span>
          {focus === undefined ? (
            <span aria-current="page">{activeName(muscle, isEnglish)}</span>
          ) : (
            <button type="button" onClick={onMuscle}>{activeName(muscle, isEnglish)}</button>
          )}
        </>
      )}
      {focus !== undefined && (
        <>
          <span aria-hidden="true">←</span>
          <span aria-current="page">{activeName(focus, isEnglish)}</span>
        </>
      )}
    </nav>
  );
}

function CategoryButton({
  category,
  active,
  isEnglish,
  onClick,
  kind,
  compact = false,
}: {
  category: { name_en: string; name_fa: string };
  active: boolean;
  isEnglish: boolean;
  onClick: () => void;
  kind: "region" | "muscle" | "focus";
  compact?: boolean;
}) {
  return (
    <button
      className={`${kind}-button${compact ? " is-compact" : ""}${active ? " is-active" : ""}`}
      type="button"
      aria-pressed={active}
      onClick={onClick}
    >
      <span dir={isEnglish ? "ltr" : "rtl"}>{activeName(category, isEnglish)}</span>
      <small dir={isEnglish ? "rtl" : "ltr"}>{secondaryName(category, isEnglish)}</small>
    </button>
  );
}

function ExerciseCard({
  exercise,
  categories,
  isEnglish,
  catalogSearch,
  isAdmin,
  returnTo,
  onDelete,
}: {
  exercise: CatalogExercise;
  categories: ExerciseCategories;
  isEnglish: boolean;
  catalogSearch: string;
  isAdmin: boolean;
  returnTo: string;
  onDelete: (exercise: CatalogExercise, trigger: HTMLButtonElement) => void;
}) {
  const { t } = useTranslation();
  const name = isEnglish ? exercise.name_en : exercise.name_fa;
  const secondary = isEnglish ? exercise.name_fa : exercise.name_en;
  const muscle = findMuscleCategory(categories, exercise.primary_muscle);
  const focus = exercise.primary_muscle === null || exercise.muscle_focus === null
    ? undefined
    : categories.muscle_focuses[exercise.primary_muscle].find(
        (category) => category.value === exercise.muscle_focus,
      );
  const equipmentNames = exercise.equipment.map((value) => t(`catalog.equipment.${value}`));
  const detailPath = `/exercises/${exercise.slug}${catalogSearch ? `?${catalogSearch}` : ""}`;

  return (
    <article className="exercise-card" aria-label={name}>
      <div className="exercise-card__media">
        <ExerciseMedia path={exercise.media_path} name={name} mediaType={exercise.media_type} />
        <span>{t(`catalog.difficulty.${exercise.difficulty}`)}</span>
      </div>
      <div className="exercise-card__body">
        <div className="exercise-card__title">
          <h3 dir={isEnglish ? "ltr" : "rtl"}>{name}</h3>
          <p dir={isEnglish ? "rtl" : "ltr"}>{secondary}</p>
        </div>
        <dl>
          <div>
            <dt>{t("catalog.primaryMuscleLabel")}</dt>
            <dd>
              {exercise.primary_muscle === null
                ? t("catalog.needsReview")
                : muscle === undefined
                  ? exercise.primary_muscle
                  : activeName(muscle, isEnglish)}
            </dd>
          </div>
          <div>
            <dt>{t("catalog.equipmentLabel")}</dt>
            <dd>{equipmentNames.join(t("catalog.listSeparator"))}</dd>
          </div>
          {focus !== undefined && (
            <div>
              <dt>{t("catalog.muscleFocusLabel")}</dt>
              <dd>{activeName(focus, isEnglish)}</dd>
            </div>
          )}
        </dl>
        <Link className="exercise-card__link" to={detailPath}>
          {t("catalog.viewExercise")}
          <span aria-hidden="true">←</span>
        </Link>
        {isAdmin && (
          <Link
            className="exercise-card__edit"
            to={`/admin/exercises/${exercise.id}/edit?${new URLSearchParams({ return_to: returnTo }).toString()}`}
          >
            {t("catalog.editExercise")}
          </Link>
        )}
        {isAdmin && (
          <button
            className="exercise-card__delete"
            type="button"
            onClick={(event) => onDelete(exercise, event.currentTarget)}
          >
            {t("catalog.deleteExercise")}
          </button>
        )}
        {isAdmin && exercise.is_active === false && (
          <span className="exercise-card__admin-state">{t("catalog.adminStatus.inactive")}</span>
        )}
        {isAdmin && exercise.needs_review === true && (
          <span className="exercise-card__admin-state">{t("catalog.needsReview")}</span>
        )}
      </div>
    </article>
  );
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5" />
    </svg>
  );
}

function StatusPanel({
  role,
  message,
  action,
  onAction,
  compact = false,
}: {
  role: "status" | "alert";
  message: string;
  action?: string;
  onAction?: () => void;
  compact?: boolean;
}) {
  return (
    <div className={`catalog-status${compact ? " catalog-status--compact" : ""}`} role={role}>
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

function parseCatalogQuery(searchParams: URLSearchParams): CatalogQuery {
  const rawPage = Number(searchParams.get("page"));
  return {
    body_region: optionalValue(searchParams.get("body_region"), bodyRegions),
    primary_muscle: optionalValue(searchParams.get("primary_muscle"), muscleGroups),
    muscle_focus: optionalValue(searchParams.get("muscle_focus"), muscleFocuses),
    equipment: optionalValue(searchParams.get("equipment"), equipment),
    difficulty: optionalValue(searchParams.get("difficulty"), difficulties),
    exercise_type: optionalValue(searchParams.get("exercise_type"), ["mobility"] as const),
    labels: parseLabels(searchParams),
    search: searchParams.get("search") || undefined,
    admin_status: optionalValue(searchParams.get("admin_status"), ["all", "inactive", "needs_review"] as const),
    page: Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1,
  };
}

function serializeCatalogQuery(query: CatalogQuery): URLSearchParams {
  const searchParams = new URLSearchParams();
  if (query.body_region !== undefined) searchParams.set("body_region", query.body_region);
  if (query.primary_muscle !== undefined) {
    searchParams.set("primary_muscle", query.primary_muscle);
  }
  if (query.muscle_focus !== undefined) searchParams.set("muscle_focus", query.muscle_focus);
  if (query.equipment !== undefined) searchParams.set("equipment", query.equipment);
  if (query.difficulty !== undefined) searchParams.set("difficulty", query.difficulty);
  if (query.exercise_type !== undefined) searchParams.set("exercise_type", query.exercise_type);
  query.labels?.forEach((label) => searchParams.append("labels", label));
  if (query.search?.trim()) searchParams.set("search", query.search);
  if (query.admin_status !== undefined) searchParams.set("admin_status", query.admin_status);
  if (query.page > 1) searchParams.set("page", String(query.page));
  return searchParams;
}

function parseLabels(searchParams: URLSearchParams): ExerciseLabel[] | undefined {
  const labels = searchParams.getAll("labels").filter(
    (value): value is ExerciseLabel => value === "full_body" || value === "cardio",
  );
  return labels.length > 0 ? labels : undefined;
}

function resultHeading(
  query: CatalogQuery,
  muscle: ExerciseCategory | undefined,
  focus: MuscleFocusCategory | undefined,
  isEnglish: boolean,
  t: (key: string) => string,
): string {
  if (query.labels?.[0] !== undefined) return t(`catalog.label.${query.labels[0]}`);
  if (query.exercise_type === "mobility") return t("catalog.mobility");
  if (focus !== undefined) return activeName(focus, isEnglish);
  return muscle === undefined ? t("catalog.title") : activeName(muscle, isEnglish);
}

function optionalValue<T extends string>(value: string | null, values: readonly T[]): T | undefined {
  return values.includes(value as T) ? (value as T) : undefined;
}

function activeName(
  category: { name_en: string; name_fa: string },
  isEnglish: boolean,
): string {
  return isEnglish ? category.name_en : category.name_fa;
}

function secondaryName(
  category: { name_en: string; name_fa: string },
  isEnglish: boolean,
): string {
  return isEnglish ? category.name_fa : category.name_en;
}

function findMuscleCategory(
  categories: ExerciseCategories,
  value: MuscleGroup | null,
): ExerciseCategory | undefined {
  if (value === null) return undefined;
  return [...categories.upper_body, ...categories.lower_body, ...categories.core].find(
    (category) => category.value === value,
  );
}
