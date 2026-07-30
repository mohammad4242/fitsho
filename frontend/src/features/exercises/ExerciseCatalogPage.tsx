import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";

import heroStrengthFallback from "../../assets/landing/hero-strength-fallback.jpg";
import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import { MemberHeaderMedia } from "../../shared/MemberHeaderMedia";
import { getExerciseCategories, getExercises } from "./api";
import { ExerciseMedia } from "./ExerciseMedia";
import {
  bodyRegions,
  difficulties,
  equipment,
  muscleGroups,
  type BodyRegion,
  type Difficulty,
  type Equipment,
  type ExerciseCategories,
  type ExerciseCategory,
  type ExerciseFilters,
  type ExerciseLabel,
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
  equipment?: Equipment;
  difficulty?: Difficulty;
  exercise_type?: ExerciseType;
  labels?: ExerciseLabel[];
  search?: string;
  page: number;
};

export function ExerciseCatalogPage() {
  const { i18n, t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [categories, setCategories] = useState<ExerciseCategories | null>(null);
  const [categoryState, setCategoryState] = useState<LoadState>("loading");
  const [categoryRetry, setCategoryRetry] = useState(0);
  const [exercisePage, setExercisePage] = useState<PaginatedExercises | null>(null);
  const [exerciseState, setExerciseState] = useState<LoadState>("idle");
  const [exerciseRetry, setExerciseRetry] = useState(0);

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
  const selectedLabel = query.labels?.[0];
  const hasSpecialFilter = selectedLabel !== undefined || query.exercise_type === "mobility";
  const canLoadExercises = hasSpecialFilter || (regionCategory !== undefined && selectedMuscle !== undefined);

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
      equipment: query.equipment,
      difficulty: query.difficulty,
      exercise_type: query.exercise_type,
      labels: query.labels,
      search: query.search?.trim() || undefined,
      page: query.page,
    };
    void getExercises(filters)
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
    canLoadExercises,
    query.body_region,
    query.difficulty,
    query.exercise_type,
    query.equipment,
    query.labels,
    query.page,
    query.search,
    selectedMuscle,
  ]);

  function writeQuery(
    changes: Partial<Omit<CatalogQuery, "page">> & { page?: number },
    resetPage = true,
  ) {
    const next = { ...query, ...changes };
    if (resetPage) next.page = 1;
    setSearchParams(serializeCatalogQuery(next));
  }

  function chooseRegion(value: BodyRegion) {
    writeQuery({ body_region: value, primary_muscle: undefined, labels: undefined, exercise_type: undefined });
  }

  function chooseMuscle(value: MuscleGroup) {
    writeQuery({ primary_muscle: value, labels: undefined, exercise_type: undefined });
  }

  function chooseSpecialFilter(changes: Pick<CatalogQuery, "labels" | "exercise_type">) {
    writeQuery({ ...changes, body_region: undefined, primary_muscle: undefined });
  }

  function resetLibrary() {
    setSearchParams(new URLSearchParams());
  }

  function resetToRegion() {
    writeQuery({ primary_muscle: undefined });
  }

  const hasResultFilters = Boolean(query.equipment || query.difficulty || query.search?.trim());
  const currentSearch = searchParams.toString();

  return (
    <div className="exercise-catalog-shell">
      <MemberHeaderMedia imageSrc={heroStrengthFallback} className="member-page-background" />
      <AuthenticatedHeader />
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
          isEnglish={isEnglish}
          onLibrary={resetLibrary}
          onRegion={resetToRegion}
        />

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
          </>
        )}

        {canLoadExercises && (
          <section className="catalog-results" aria-labelledby="results-heading">
            <div className="catalog-stage__heading catalog-stage__heading--results">
              <span>03</span>
              <div>
                <h2 id="results-heading" className="fitsho-display">
                  {resultHeading(query, muscleCategory, isEnglish, t)}
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
    </div>
  );
}

function CatalogBreadcrumb({
  region,
  muscle,
  isEnglish,
  onLibrary,
  onRegion,
}: {
  region?: { name_en: string; name_fa: string };
  muscle?: ExerciseCategory;
  isEnglish: boolean;
  onLibrary: () => void;
  onRegion: () => void;
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
          <span aria-current="page">{activeName(muscle, isEnglish)}</span>
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
  kind: "region" | "muscle";
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
}: {
  exercise: ExerciseSummary;
  categories: ExerciseCategories;
  isEnglish: boolean;
  catalogSearch: string;
}) {
  const { t } = useTranslation();
  const name = isEnglish ? exercise.name_en : exercise.name_fa;
  const secondary = isEnglish ? exercise.name_fa : exercise.name_en;
  const muscle = findMuscleCategory(categories, exercise.primary_muscle);
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
        </dl>
        <Link className="exercise-card__link" to={detailPath}>
          {t("catalog.viewExercise")}
          <span aria-hidden="true">←</span>
        </Link>
      </div>
    </article>
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
    equipment: optionalValue(searchParams.get("equipment"), equipment),
    difficulty: optionalValue(searchParams.get("difficulty"), difficulties),
    exercise_type: optionalValue(searchParams.get("exercise_type"), ["mobility"] as const),
    labels: parseLabels(searchParams),
    search: searchParams.get("search") || undefined,
    page: Number.isInteger(rawPage) && rawPage >= 1 ? rawPage : 1,
  };
}

function serializeCatalogQuery(query: CatalogQuery): URLSearchParams {
  const searchParams = new URLSearchParams();
  if (query.body_region !== undefined) searchParams.set("body_region", query.body_region);
  if (query.primary_muscle !== undefined) {
    searchParams.set("primary_muscle", query.primary_muscle);
  }
  if (query.equipment !== undefined) searchParams.set("equipment", query.equipment);
  if (query.difficulty !== undefined) searchParams.set("difficulty", query.difficulty);
  if (query.exercise_type !== undefined) searchParams.set("exercise_type", query.exercise_type);
  query.labels?.forEach((label) => searchParams.append("labels", label));
  if (query.search?.trim()) searchParams.set("search", query.search);
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
  isEnglish: boolean,
  t: (key: string) => string,
): string {
  if (query.labels?.[0] !== undefined) return t(`catalog.label.${query.labels[0]}`);
  if (query.exercise_type === "mobility") return t("catalog.mobility");
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
