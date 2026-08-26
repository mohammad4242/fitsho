import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { getExerciseCategories } from "../exercises/api";
import { ExerciseMedia } from "../exercises/ExerciseMedia";
import "../exercises/exercises.css";
import type {
  BodyRegion,
  ExerciseCategories,
  MuscleFocus,
  MuscleGroup,
} from "../exercises/types";
import { getAdminExercises } from "./api";
import type { AdminExercise } from "./types";

export interface ExerciseLibraryPickerModalProps {
  filterExercise?: (exercise: AdminExercise) => boolean;
  isOpen: boolean;
  onClose: () => void;
  onSelect: (exercise: AdminExercise) => void;
  title?: string;
}

type Stage = "region" | "muscle" | "focus" | "exercises";

export function ExerciseLibraryPickerModal({
  filterExercise,
  isOpen,
  onClose,
  onSelect,
  title,
}: ExerciseLibraryPickerModalProps) {
  const { i18n, t } = useTranslation();
  const isEn = i18n.resolvedLanguage === "en";

  const [categories, setCategories] = useState<ExerciseCategories | null>(null);
  const [categoriesLoading, setCategoriesLoading] = useState(false);

  const [selectedRegion, setSelectedRegion] = useState<BodyRegion | null>(null);
  const [selectedMuscle, setSelectedMuscle] = useState<MuscleGroup | null>(null);
  const [selectedFocus, setSelectedFocus] = useState<MuscleFocus | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  const [exercises, setExercises] = useState<AdminExercise[]>([]);
  const [exercisesLoading, setExercisesLoading] = useState(false);

  const modalRef = useRef<HTMLDivElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  // Debounce search query
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(searchQuery.trim());
    }, 200);
    return () => window.clearTimeout(timer);
  }, [searchQuery]);

  // Load categories when modal opens
  useEffect(() => {
    if (!isOpen) return;
    let active = true;
    setCategoriesLoading(true);
    void getExerciseCategories()
      .then((data) => {
        if (active) {
          setCategories(data);
          setCategoriesLoading(false);
        }
      })
      .catch(() => {
        if (active) setCategoriesLoading(false);
      });
    return () => {
      active = false;
    };
  }, [isOpen]);

  // Reset state when opening
  useEffect(() => {
    if (isOpen) {
      setSelectedRegion(null);
      setSelectedMuscle(null);
      setSelectedFocus(null);
      setSearchQuery("");
      setDebouncedSearch("");
      setExercises([]);
    }
  }, [isOpen]);

  // Handle escape key
  useEffect(() => {
    if (!isOpen) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Fetch exercises on hierarchical selection or search
  useEffect(() => {
    if (!isOpen) return;

    const isSearching = debouncedSearch.length >= 2;
    const hasCategorySelection = selectedRegion !== null && selectedMuscle !== null;

    if (!isSearching && !hasCategorySelection) {
      setExercises([]);
      return;
    }

    let active = true;
    setExercisesLoading(true);

    const filters = isSearching
      ? {
          search: debouncedSearch,
          content_type: "exercise" as const,
          is_active: true,
          is_programmable: true,
          page_size: 30,
        }
      : {
          content_type: "exercise" as const,
          body_region: selectedRegion ?? undefined,
          primary_muscle: selectedMuscle ?? undefined,
          muscle_focus: selectedFocus ?? undefined,
          is_active: true,
          is_programmable: true,
          page_size: 50,
        };

    void getAdminExercises(filters)
      .then((res) => {
        if (active) {
          setExercises(res.items);
          setExercisesLoading(false);
        }
      })
      .catch(() => {
        if (active) {
          setExercises([]);
          setExercisesLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [debouncedSearch, isOpen, selectedFocus, selectedMuscle, selectedRegion]);

  const visibleExercises = filterExercise
    ? exercises.filter(filterExercise)
    : exercises;

  // Determine available muscles for selected region
  const availableMuscles = useMemo(() => {
    if (!categories || !selectedRegion) return [];
    return categories[selectedRegion] ?? [];
  }, [categories, selectedRegion]);

  // Determine available focuses for selected muscle
  const availableFocuses = useMemo(() => {
    if (!categories || !selectedMuscle) return [];
    return categories.muscle_focuses[selectedMuscle] ?? [];
  }, [categories, selectedMuscle]);

  // Determine current stage when not searching
  const currentStage: Stage = useMemo(() => {
    if (selectedRegion === null) return "region";
    if (selectedMuscle === null) return "muscle";
    if (availableFocuses.length > 0 && selectedFocus === null) return "focus";
    return "exercises";
  }, [availableFocuses.length, selectedFocus, selectedMuscle, selectedRegion]);

  const isSearching = debouncedSearch.length >= 2;

  function handleSelectRegion(region: BodyRegion) {
    setSelectedRegion(region);
    setSelectedMuscle(null);
    setSelectedFocus(null);
  }

  function handleSelectMuscle(muscle: MuscleGroup) {
    setSelectedMuscle(muscle);
    setSelectedFocus(null);
  }

  function handleSelectFocus(focus: MuscleFocus | null) {
    setSelectedFocus(focus);
  }

  function handleBack() {
    if (currentStage === "exercises") {
      if (availableFocuses.length > 0) {
        setSelectedFocus(null);
      } else {
        setSelectedMuscle(null);
      }
    } else if (currentStage === "focus") {
      setSelectedMuscle(null);
    } else if (currentStage === "muscle") {
      setSelectedRegion(null);
    }
  }

  function handleResetHierarchy() {
    setSelectedRegion(null);
    setSelectedMuscle(null);
    setSelectedFocus(null);
  }

  if (!isOpen) return null;

  const regionObj = categories?.body_regions.find((r) => r.value === selectedRegion);
  const muscleObj = availableMuscles.find((m) => m.value === selectedMuscle);
  const focusObj = availableFocuses.find((f) => f.value === selectedFocus);

  return (
    <div
      className="admin-exercise-picker-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <section
        aria-label={title || t("admin.templateEditor.exercisePicker")}
        aria-modal="true"
        className="admin-exercise-picker-dialog"
        ref={modalRef}
        role="dialog"
      >
        <header className="admin-exercise-picker-header">
          <div>
            <span className="eyebrow eyebrow--accent">
              {t("admin.templateEditor.exercisePickerEyebrow", "کتابخانه حرکات")}
            </span>
            <h2>{title || t("admin.templateEditor.exercisePicker")}</h2>
          </div>
          <button
            aria-label={t("admin.templateEditor.close")}
            className="admin-exercise-picker-close"
            onClick={onClose}
            type="button"
          >
            ✕
          </button>
        </header>

        <div className="admin-exercise-picker-search-bar">
          <label className="admin-field">
            <span>{t("admin.templateEditor.searchLabel", "جست‌وجوی سریع")}</span>
            <input
              autoFocus
              dir="auto"
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t(
                "admin.templateEditor.searchPlaceholder",
                "جست‌وجو با نام فارسی یا انگلیسی…",
              )}
              ref={searchInputRef}
              type="search"
              value={searchQuery}
            />
          </label>
        </div>

        {!isSearching && (
          <nav aria-label={t("admin.templateEditor.breadcrumb", "مسیر انتخاب حرکت")} className="admin-exercise-picker-breadcrumbs">
            <button
              className={selectedRegion === null ? "is-current" : ""}
              onClick={handleResetHierarchy}
              type="button"
            >
              {t("admin.templateEditor.libraryRoot", "کتابخانه")}
            </button>
            {regionObj && (
              <>
                <span className="admin-breadcrumb-separator">›</span>
                <button
                  className={selectedMuscle === null ? "is-current" : ""}
                  onClick={() => {
                    setSelectedMuscle(null);
                    setSelectedFocus(null);
                  }}
                  type="button"
                >
                  {isEn ? regionObj.name_en : regionObj.name_fa}
                </button>
              </>
            )}
            {muscleObj && (
              <>
                <span className="admin-breadcrumb-separator">›</span>
                <button
                  className={selectedFocus === null && availableFocuses.length > 0 ? "is-current" : ""}
                  onClick={() => setSelectedFocus(null)}
                  type="button"
                >
                  {isEn ? muscleObj.name_en : muscleObj.name_fa}
                </button>
              </>
            )}
            {focusObj && (
              <>
                <span className="admin-breadcrumb-separator">›</span>
                <span className="admin-breadcrumb-current">
                  {isEn ? focusObj.name_en : focusObj.name_fa}
                </span>
              </>
            )}
          </nav>
        )}

        <div className="admin-exercise-picker-content">
          {categoriesLoading && (
            <p className="admin-status" role="status">
              {t("catalog.loadingCategories", "در حال دریافت دسته‌بندی‌ها…")}
            </p>
          )}

          {/* SEARCH RESULTS VIEW */}
          {isSearching && (
            <div className="admin-exercise-picker-search-results">
              <h3 className="admin-picker-stage-title">
                {t("catalog.searchLabel", "نتایج جست‌وجو")} ({visibleExercises.length})
              </h3>
              {exercisesLoading && (
                <p className="admin-status" role="status">
                  {t("catalog.loadingExercises", "در حال دریافت حرکت‌ها…")}
                </p>
              )}
              {!exercisesLoading && visibleExercises.length === 0 && (
                <p className="admin-status">
                  {t("catalog.noMatches", "حرکتی با این مشخصات یافت نشد.")}
                </p>
              )}
              <div className="admin-exercise-picker-list">
                {visibleExercises.map((exercise) => (
                  <ExercisePickerItem
                    exercise={exercise}
                    isEn={isEn}
                    key={exercise.id}
                    onSelect={() => onSelect(exercise)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* HIERARCHICAL NAVIGATION VIEW */}
          {!isSearching && !categoriesLoading && categories && (
            <>
              {/* STAGE 1: BODY REGION */}
              {currentStage === "region" && (
                <div className="admin-picker-stage">
                  <h3 className="admin-picker-stage-title">
                    {t("admin.templateEditor.selectRegion", "۱. انتخاب ناحیه بدن")}
                  </h3>
                  <div className="region-selector" role="group" aria-label={t("catalog.regionTitle")}>
                    {categories.body_regions.map((region) => (
                      <PickerCategoryButton
                        active={region.value === selectedRegion}
                        category={region}
                        isEnglish={isEn}
                        key={region.value}
                        kind="region"
                        onClick={() => handleSelectRegion(region.value)}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* STAGE 2: MUSCLE GROUP */}
              {currentStage === "muscle" && (
                <div className="admin-picker-stage">
                  <div className="admin-picker-stage-header">
                    <button className="admin-picker-back-btn" onClick={handleBack} type="button">
                      ← {t("admin.templateEditor.backButton", "بازگشت")}
                    </button>
                    <h3 className="admin-picker-stage-title">
                      {t("admin.templateEditor.selectMuscle", "۲. انتخاب عضله")}
                    </h3>
                  </div>
                  <div className="muscle-selector" role="group" aria-label={t("catalog.muscleTitle")}>
                    {availableMuscles.map((muscle) => (
                      <PickerCategoryButton
                        active={muscle.value === selectedMuscle}
                        category={muscle}
                        compact={muscle.value === "forearms" || muscle.value === "neck"}
                        isEnglish={isEn}
                        key={muscle.value}
                        kind="muscle"
                        onClick={() => handleSelectMuscle(muscle.value)}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* STAGE 3: MUSCLE FOCUS */}
              {currentStage === "focus" && (
                <div className="admin-picker-stage">
                  <div className="admin-picker-stage-header">
                    <button className="admin-picker-back-btn" onClick={handleBack} type="button">
                      ← {t("admin.templateEditor.backButton", "بازگشت")}
                    </button>
                    <h3 className="admin-picker-stage-title">
                      {t("admin.templateEditor.selectFocus", "۳. انتخاب بخش یا تمرکز عضله")}
                    </h3>
                  </div>
                  <div className="focus-selector" role="group" aria-label={t("catalog.focusTitle")}>
                    <button
                      aria-pressed={selectedFocus === null}
                      className={`focus-button admin-picker-cat-btn${selectedFocus === null ? " is-active" : ""}`}
                      onClick={() => handleSelectFocus(null)}
                      type="button"
                    >
                      <span className="admin-picker-cat-name" dir={isEn ? "ltr" : "rtl"}>
                        {t("admin.templateEditor.allMuscleExercises", "همه حرکات این عضله")}
                      </span>
                      <small className="admin-picker-cat-alt" dir={isEn ? "rtl" : "ltr"}>
                        {isEn ? muscleObj?.name_en : muscleObj?.name_fa}
                      </small>
                    </button>
                    {availableFocuses.map((focus) => (
                      <PickerCategoryButton
                        active={focus.value === selectedFocus}
                        category={focus}
                        isEnglish={isEn}
                        key={focus.value}
                        kind="focus"
                        onClick={() => handleSelectFocus(focus.value)}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* STAGE 4: EXERCISES LIST */}
              {currentStage === "exercises" && (
                <div className="admin-picker-stage">
                  <div className="admin-picker-stage-header">
                    <button className="admin-picker-back-btn" onClick={handleBack} type="button">
                      ← {t("admin.templateEditor.backButton", "بازگشت")}
                    </button>
                    <h3 className="admin-picker-stage-title">
                      {t("admin.templateEditor.selectMovement", "۴. انتخاب حرکت")} ({visibleExercises.length})
                    </h3>
                  </div>
                  {exercisesLoading && (
                    <p className="admin-status" role="status">
                      {t("catalog.loadingExercises", "در حال دریافت حرکت‌ها…")}
                    </p>
                  )}
                  {!exercisesLoading && visibleExercises.length === 0 && (
                    <p className="admin-status">
                      {t("catalog.emptyGroup", "حرکتی در این دسته ثبت نشده است.")}
                    </p>
                  )}
                  <div className="admin-exercise-picker-list">
                    {visibleExercises.map((exercise) => (
                      <ExercisePickerItem
                        exercise={exercise}
                        isEn={isEn}
                        key={exercise.id}
                        onSelect={() => onSelect(exercise)}
                      />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </section>
    </div>
  );
}

function PickerCategoryButton({
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
  const primaryName = isEnglish ? category.name_en : category.name_fa;
  const secondaryName = isEnglish ? category.name_fa : category.name_en;

  return (
    <button
      aria-pressed={active}
      className={`${kind}-button admin-picker-cat-btn${compact ? " is-compact" : ""}${active ? " is-active" : ""}`}
      onClick={onClick}
      type="button"
    >
      <span className="admin-picker-cat-name" dir={isEnglish ? "ltr" : "rtl"}>
        {primaryName}
      </span>
      <small className="admin-picker-cat-alt" dir={isEnglish ? "rtl" : "ltr"}>
        {secondaryName}
      </small>
    </button>
  );
}

function ExercisePickerItem({
  exercise,
  isEn,
  onSelect,
}: {
  exercise: AdminExercise;
  isEn: boolean;
  onSelect: () => void;
}) {
  const { t } = useTranslation();
  const primaryName = isEn ? exercise.name_en : exercise.name_fa;
  const secondaryName = isEn ? exercise.name_fa : exercise.name_en;

  return (
    <button
      aria-label={t("admin.templateEditor.selectExercise", { name: primaryName })}
      className="admin-exercise-picker-item"
      onClick={onSelect}
      type="button"
    >
      <div className="admin-exercise-picker-item__media">
        {exercise.media_path && (
          <ExerciseMedia
            ambient
            mediaType={exercise.media_type}
            name={primaryName}
            path={exercise.media_path}
          />
        )}
      </div>
      <div className="admin-exercise-picker-item__info">
        <strong className="admin-exercise-picker-item__name" dir={isEn ? "ltr" : "rtl"}>
          {primaryName}
        </strong>
        <span className="admin-exercise-picker-item__alt" dir={isEn ? "rtl" : "ltr"}>
          {secondaryName}
        </span>
      </div>
      <div className="admin-exercise-picker-item__tags">
        {exercise.movement_pattern && (
          <span className="admin-badge admin-badge--pattern">
            {t(`admin.programming.movementPattern.${exercise.movement_pattern}`, exercise.movement_pattern)}
          </span>
        )}
        {exercise.equipment && exercise.equipment.length > 0 && (
          <span className="admin-badge admin-badge--equipment">
            {t(`catalog.equipment.${exercise.equipment[0]}`, exercise.equipment[0])}
          </span>
        )}
        {exercise.needs_review && (
          <span className="admin-badge admin-badge--review">
            {t("admin.templates.reviewMedia", "بازبینی رسانه")}
          </span>
        )}
      </div>
    </button>
  );
}
