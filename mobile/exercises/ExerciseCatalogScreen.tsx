import { useQuery } from "@tanstack/react-query";
import { useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  type PressableStateCallbackType,
  type StyleProp,
  type ViewStyle,
} from "react-native";

import type {
  BodyRegion,
  Difficulty,
  Equipment,
  ExerciseContentType,
  ExerciseLabel,
  ExerciseType,
  MuscleFocus,
  MuscleGroup,
} from "@fitician/core/exercises";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { exerciseKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import { PerformanceMeasuredCommit } from "../platform/performanceMeasuredCommit";
import { getMobileViewState, type MobileViewState } from "../ui/requestState";
import {
  Button,
  Card,
  EmptyState,
  Notice,
  SegmentedControl,
  ScreenHeader,
  Sheet,
  Skeleton,
  TextField,
} from "../ui/components";
import { Screen } from "../ui/layout";
import { fiticianTokens } from "../ui/tokens";
import {
  createExerciseApi,
  type ExerciseCategories,
  type ExerciseFilters,
  type ExerciseSummary,
  type PaginatedExercises,
} from "./exerciseApi";
import { exerciseCopy, exerciseSecondaryTitle, exerciseTitle, formatExerciseCount } from "./exerciseCopy";
import { ExerciseMedia } from "./ExerciseMedia";

type CatalogSelection = {
  readonly bodyRegion: BodyRegion | null;
  readonly contentType: ExerciseContentType;
  readonly difficulty: Difficulty | null;
  readonly equipment: Equipment | null;
  readonly exerciseType: ExerciseType | null;
  readonly label: ExerciseLabel | null;
  readonly muscleFocus: MuscleFocus | null;
  readonly primaryMuscle: MuscleGroup | null;
  readonly search: string;
};

type ActiveFilterKey =
  | "bodyRegion"
  | "contentType"
  | "difficulty"
  | "equipment"
  | "exerciseType"
  | "label"
  | "muscleFocus"
  | "primaryMuscle"
  | "search";

type ActiveFilter = {
  readonly key: ActiveFilterKey;
  readonly label: string;
};

const initialSelection: CatalogSelection = {
  bodyRegion: null,
  contentType: "exercise",
  difficulty: null,
  equipment: null,
  exerciseType: null,
  label: null,
  muscleFocus: null,
  primaryMuscle: null,
  search: "",
};

const pageSize = 12;

export function ExerciseCatalogScreen() {
  const auth = useMobileAuth();
  const router = useRouter();
  const api = useMemo(() => createExerciseApi(auth.request), [auth.request]);
  const connectivityStatus = useConnectivityStatus();
  const [selection, setSelection] = useState<CatalogSelection>(initialSelection);
  const [page, setPage] = useState(1);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [showAll, setShowAll] = useState(false);

  const filters = useMemo<ExerciseFilters>(() => {
    const next: ExerciseFilters = {
      content_type: selection.contentType,
      page,
      page_size: pageSize,
    };
    if (selection.bodyRegion !== null) next.body_region = selection.bodyRegion;
    if (selection.primaryMuscle !== null) next.primary_muscle = selection.primaryMuscle;
    if (selection.muscleFocus !== null) next.muscle_focus = selection.muscleFocus;
    if (selection.equipment !== null) next.equipment = selection.equipment;
    if (selection.difficulty !== null) next.difficulty = selection.difficulty;
    if (selection.exerciseType !== null) next.exercise_type = selection.exerciseType;
    if (selection.label !== null) next.labels = [selection.label];
    const search = selection.search.trim();
    if (search) next.search = search;
    return next;
  }, [page, selection]);

  const categoriesQuery = useQuery({
    queryFn: api.getCategories,
    queryKey: exerciseKeys.categories(),
  });
  const hasSearch = selection.search.trim().length > 0;
  const hasSpecialFilter = selection.label !== null || selection.exerciseType === "mobility";
  const hasGuidedSelection = selection.bodyRegion !== null && selection.primaryMuscle !== null;
  const canLoadExercises = showAll || hasSearch || hasSpecialFilter || hasGuidedSelection;
  const exercisesQuery = useQuery({
    enabled: canLoadExercises,
    queryFn: () => api.list(filters),
    queryKey: exerciseKeys.list(filters),
  });
  const categoriesState = getMobileViewState(categoriesQuery, { connectivityStatus });
  const exercisesState = getMobileViewState(exercisesQuery, {
    connectivityStatus,
    isEmpty: (data) => data.items.length === 0,
  });
  const categories = viewData(categoriesState);
  const exercisePage = viewData(exercisesState);
  const availableMuscles = categories === undefined || selection.bodyRegion === null
    ? []
    : musclesForRegion(categories, selection.bodyRegion);
  const availableFocuses = categories === undefined || selection.primaryMuscle === null
    ? []
    : categories.muscle_focuses[selection.primaryMuscle] ?? [];
  const activeFilters = useMemo(
    () => getActiveFilters(selection, categories),
    [categories, selection],
  );
  const advancedFilterCount = [selection.equipment, selection.difficulty, selection.exerciseType]
    .filter((value) => value !== null && value !== "mobility").length;

  useEffect(() => {
    if (
      selection.primaryMuscle !== null &&
      availableMuscles.every((category) => category.value !== selection.primaryMuscle)
    ) {
      setSelection((current) => ({ ...current, muscleFocus: null, primaryMuscle: null }));
      setPage(1);
    }
  }, [availableMuscles, selection.primaryMuscle]);

  function updateSelection(changes: Partial<CatalogSelection>) {
    setSelection((current) => ({ ...current, ...changes }));
    setPage(1);
  }

  function chooseBodyRegion(bodyRegion: BodyRegion) {
    setShowAll(false);
    updateSelection({
      bodyRegion,
      contentType: "exercise",
      exerciseType: null,
      label: null,
      muscleFocus: null,
      primaryMuscle: null,
    });
  }

  function chooseMuscle(primaryMuscle: MuscleGroup) {
    setShowAll(false);
    updateSelection({ muscleFocus: null, primaryMuscle });
  }

  function chooseSpecialFilter(changes: Pick<CatalogSelection, "exerciseType" | "label">) {
    setShowAll(false);
    updateSelection({
      ...changes,
      bodyRegion: null,
      muscleFocus: null,
      primaryMuscle: null,
    });
  }

  function clearFilters() {
    setShowAll(false);
    setSelection(initialSelection);
    setPage(1);
  }

  function showAllExercises() {
    setShowAll(true);
    setSelection(initialSelection);
    setPage(1);
  }

  function removeFilter(key: ActiveFilterKey) {
    if (key === "bodyRegion") {
      updateSelection({ bodyRegion: null, muscleFocus: null, primaryMuscle: null });
      return;
    }
    if (key === "primaryMuscle") {
      updateSelection({ muscleFocus: null, primaryMuscle: null });
      return;
    }
    if (key === "contentType") {
      updateSelection({ contentType: "exercise" });
      return;
    }
    if (key === "search") {
      updateSelection({ search: "" });
      return;
    }
    if (key === "difficulty") {
      updateSelection({ difficulty: null });
      return;
    }
    if (key === "equipment") {
      updateSelection({ equipment: null });
      return;
    }
    if (key === "exerciseType") {
      updateSelection({ exerciseType: null });
      return;
    }
    if (key === "label") {
      updateSelection({ label: null });
      return;
    }
    updateSelection({ muscleFocus: null });
  }

  function openExercise(exercise: ExerciseSummary) {
    router.push({ pathname: "/member/exercises/[slug]", params: { slug: exercise.slug } });
  }

  return (
    <Screen contentWidth="reading" contentContainerStyle={styles.screen}>
      <ScreenHeader
        compact
        eyebrow="حرکت مناسب امروزت را پیدا کن"
        subtitle={exerciseCopy.catalogIntro}
        title={exerciseCopy.library}
      />

      <TextField
        accessibilityLabel={exerciseCopy.search}
        label={exerciseCopy.search}
        onChangeText={(search) => updateSelection({ search })}
        placeholder={exerciseCopy.searchPlaceholder}
        returnKeyType="search"
        value={selection.search}
      />

      <View style={styles.discoveryPanel}>
        <View style={styles.quickFilterRow}>
          <QuickFilterChip
            label={exerciseCopy.allExercises}
            selected={showAll}
            onPress={showAllExercises}
          />
          <QuickFilterChip
            label={exerciseCopy.fullBody}
            selected={selection.label === "full_body"}
            onPress={() => chooseSpecialFilter({ exerciseType: null, label: "full_body" })}
          />
          <QuickFilterChip
            label={exerciseCopy.labels.cardio}
            selected={selection.label === "cardio"}
            onPress={() => chooseSpecialFilter({ exerciseType: null, label: "cardio" })}
          />
          <QuickFilterChip
            label={exerciseCopy.mobility}
            selected={selection.exerciseType === "mobility"}
            onPress={() => chooseSpecialFilter({ exerciseType: "mobility", label: null })}
          />
        </View>

        {categoriesState.status === "loading" && <Skeleton height={96} />}
        {categoriesState.status === "error" && (
          <Notice
            actionLabel={exerciseCopy.retry}
            message={exerciseCopy.categoriesError}
            onAction={() => void categoriesQuery.refetch()}
            variant="danger"
          />
        )}
        {categoriesState.status === "offline" && categories === undefined && (
          <Notice message="برای دریافت دسته‌بندی‌ها به اینترنت وصل شو." variant="offline" />
        )}

        {categories !== undefined ? (
          <>
            <DiscoveryStage
              stage="01"
              title={exerciseCopy.bodyRegion}
              description={exerciseCopy.bodyRegionIntro}
            >
              <View style={styles.regionOptionRow}>
                {categories.body_regions.map((category) => (
                  <RegionOption
                    key={category.value}
                    category={category}
                    selected={selection.bodyRegion === category.value}
                    onPress={() => chooseBodyRegion(category.value)}
                  />
                ))}
              </View>
            </DiscoveryStage>

            {selection.bodyRegion !== null ? (
              <DiscoveryStage
                stage="02"
                title={exerciseCopy.muscle}
                description={exerciseCopy.muscleIntro}
              >
                <View style={styles.wrappedOptionRow}>
                  {availableMuscles.map((category) => (
                    <MuscleOption
                      key={category.value}
                      category={category}
                      selected={selection.primaryMuscle === category.value}
                      onPress={() => chooseMuscle(category.value)}
                    />
                  ))}
                </View>
              </DiscoveryStage>
            ) : null}

            {selection.primaryMuscle !== null ? (
              <DiscoveryStage
                stage="03"
                title={exerciseCopy.focus}
                description={exerciseCopy.focusIntro}
              >
                <ContentTypeSwitcher
                  value={selection.contentType}
                  onChange={(contentType) => updateSelection({ contentType, muscleFocus: null })}
                />
                {selection.contentType === "exercise" ? (
                  <View style={styles.wrappedOptionRow}>
                    <FocusOption
                      label={exerciseCopy.allMuscleFocuses}
                      selected={selection.muscleFocus === null}
                      onPress={() => updateSelection({ muscleFocus: null })}
                    />
                    {availableFocuses.map((category) => (
                      <FocusOption
                        key={category.value}
                        category={category}
                        selected={selection.muscleFocus === category.value}
                        onPress={() => updateSelection({ muscleFocus: category.value })}
                      />
                    ))}
                  </View>
                ) : null}
              </DiscoveryStage>
            ) : null}
          </>
        ) : null}

        <View style={styles.discoveryPanelFooter}>
          <Button
            hitSlop={fiticianTokens.spacing[1]}
            label={advancedFilterCount > 0
              ? `${exerciseCopy.moreFilters} · ${formatExerciseCount(advancedFilterCount)}`
              : exerciseCopy.moreFilters}
            onPress={() => setFiltersOpen(true)}
            style={styles.moreFiltersButton}
            variant="ghost"
          />
        </View>
      </View>

      {activeFilters.length > 0 ? (
        <View style={styles.activeFilters}>
          <Text accessibilityRole="header" style={styles.filterLabel}>فیلترهای فعال</Text>
          <ScrollView
            contentContainerStyle={styles.activeFilterRow}
            horizontal
            showsHorizontalScrollIndicator={false}
          >
            {activeFilters.map((filter) => (
              <ActiveFilterChip
                key={filter.key}
                label={filter.label}
                onRemove={() => removeFilter(filter.key)}
              />
            ))}
          </ScrollView>
        </View>
      ) : null}

      {canLoadExercises ? (
        <>
          <Text accessibilityRole="header" style={styles.resultsTitle}>{exerciseCopy.resultsTitle}</Text>
          <ExerciseResults
            page={exercisePage}
            state={exercisesState}
            onOpen={openExercise}
            onPageChange={setPage}
            onRetry={() => void exercisesQuery.refetch()}
          />
        </>
      ) : (
        <DiscoveryPrompt
          message={selection.bodyRegion === null
            ? exerciseCopy.selectRegionPrompt
            : exerciseCopy.selectMusclePrompt}
        />
      )}

      <Sheet
        onClose={() => setFiltersOpen(false)}
        title={exerciseCopy.advancedFilters}
        visible={filtersOpen}
      >
        <Text style={styles.filterLabel}>{exerciseCopy.equipment}</Text>
        <ChoiceRow>
          <ChoiceChip
            label="همه"
            selected={selection.equipment === null}
            onPress={() => updateSelection({ equipment: null })}
          />
          {equipmentOptions.map((value) => (
            <ChoiceChip
              key={value}
              label={exerciseCopy.equipments[value]}
              selected={selection.equipment === value}
              onPress={() => updateSelection({ equipment: value })}
            />
          ))}
        </ChoiceRow>
        <Text style={styles.filterLabel}>{exerciseCopy.difficulty}</Text>
        <ChoiceRow>
          <ChoiceChip
            label="همه"
            selected={selection.difficulty === null}
            onPress={() => updateSelection({ difficulty: null })}
          />
          {difficultyOptions.map((value) => (
            <ChoiceChip
              key={value}
              label={exerciseCopy.difficulties[value]}
              selected={selection.difficulty === value}
              onPress={() => updateSelection({ difficulty: value })}
            />
          ))}
        </ChoiceRow>
        <Text style={styles.filterLabel}>نوع حرکت</Text>
        <ChoiceRow>
          <ChoiceChip
            label="همه"
            selected={selection.exerciseType === null}
            onPress={() => updateSelection({ exerciseType: null })}
          />
          {exerciseTypeOptions.map((value) => (
            <ChoiceChip
              key={value}
              label={exerciseCopy.exerciseTypes[value]}
              selected={selection.exerciseType === value}
              onPress={() => updateSelection({ exerciseType: value, label: null })}
            />
          ))}
        </ChoiceRow>
        <View style={styles.sheetActions}>
          <Button label={exerciseCopy.clearFilters} onPress={clearFilters} variant="ghost" />
          <Button label="نمایش نتایج" onPress={() => setFiltersOpen(false)} />
        </View>
      </Sheet>
    </Screen>
  );
}

function ExerciseResults({
  onOpen,
  onPageChange,
  onRetry,
  page,
  state,
}: {
  readonly onOpen: (exercise: ExerciseSummary) => void;
  readonly onPageChange: (page: number) => void;
  readonly onRetry: () => void;
  readonly page: PaginatedExercises | undefined;
  readonly state: MobileViewState<PaginatedExercises>;
}) {
  if (state.status === "loading") {
    return (
      <View style={styles.results}>
        <Skeleton height={140} />
        <Skeleton height={140} />
      </View>
    );
  }
  if (state.status === "error") {
    return (
      <Notice
        actionLabel={exerciseCopy.retry}
        message={exerciseCopy.error}
        onAction={onRetry}
        variant="danger"
      />
    );
  }
  if (state.status === "offline" && page === undefined) {
    return <Notice message="برای دریافت حرکت‌ها به اینترنت وصل شو." variant="offline" />;
  }
  if (state.status === "empty") {
    return <EmptyState title={exerciseCopy.noResults} />;
  }
  if (page === undefined) return null;

  return (
    <View style={styles.results}>
      {state.status === "offline" ? (
        <Notice message="نمایش فهرست ذخیره‌شده؛ اتصال اینترنت برقرار نیست." variant="offline" />
      ) : state.status === "stale" ? (
        <Notice message={exerciseCopy.stale} variant="info" />
      ) : null}
      <Text style={styles.resultCount}>{formatExerciseCount(page.total)} نتیجه</Text>
      <PerformanceMeasuredCommit key={`exercise-page-${page.page}`} metric="large_list_render">
        {page.items.map((exercise) => (
          <ExerciseCard key={exercise.id} exercise={exercise} onPress={() => onOpen(exercise)} />
        ))}
      </PerformanceMeasuredCommit>
      {page.total_pages > 1 ? (
        <View style={styles.pagination}>
          <Button
            label={exerciseCopy.previousPage}
            disabled={page.page <= 1}
            onPress={() => onPageChange(Math.max(1, page.page - 1))}
            variant="secondary"
          />
          <Text style={styles.pageIndicator}>
            {formatExerciseCount(page.page)} / {formatExerciseCount(page.total_pages)}
          </Text>
          <Button
            label={exerciseCopy.nextPage}
            disabled={page.page >= page.total_pages}
            onPress={() => onPageChange(Math.min(page.total_pages, page.page + 1))}
            variant="secondary"
          />
        </View>
      ) : null}
    </View>
  );
}

function ExerciseCard({
  exercise,
  onPress,
}: {
  readonly exercise: ExerciseSummary;
  readonly onPress: () => void;
}) {
  const name = exerciseTitle(exercise.name_fa, exercise.name_en);
  return (
    <Card
      accessibilityLabel={name}
      onPress={onPress}
      style={styles.exerciseCard}
      variant="interactive"
    >
      <View style={styles.cardMedia}>
        <ExerciseMedia
          accessibilityLabel={`نمایش حرکت ${name}`}
          compact
          mediaType={exercise.media_type}
          name={name}
          path={exercise.media_path}
          style={styles.cardMediaImage}
        />
        <View pointerEvents="none" style={styles.cardMediaScrim} />
        <Text style={styles.mediaDifficulty}>{exerciseCopy.difficulties[exercise.difficulty]}</Text>
      </View>
      <View style={styles.cardHeader}>
        <View style={styles.cardCopy}>
          <Text style={styles.exerciseName}>{name}</Text>
          <Text style={styles.exerciseSecondary}>{exerciseSecondaryTitle(exercise.name_fa, exercise.name_en)}</Text>
        </View>
        <Text style={styles.contentBadge}>
          {exercise.content_type === "guide" ? exerciseCopy.guides : "حرکت"}
        </Text>
      </View>
      <View style={styles.metaRow}>
        <Text style={styles.metaText}>
          {exercise.primary_muscle === null ? "عضله بررسی نشده" : exerciseCopy.muscles[exercise.primary_muscle]}
        </Text>
        <Text style={styles.metaText}>
          {exercise.equipment.map((value) => exerciseCopy.equipments[value]).join("، ")}
        </Text>
        {exercise.muscle_focus !== null && exercise.muscle_focus !== undefined ? (
          <Text style={styles.metaText}>{exerciseCopy.muscleFocuses[exercise.muscle_focus]}</Text>
        ) : null}
      </View>
    </Card>
  );
}

function DiscoveryStage({
  children,
  description,
  stage,
  title,
}: {
  readonly children: React.ReactNode;
  readonly description?: string;
  readonly stage: string;
  readonly title: string;
}) {
  return (
    <View style={styles.discoveryStage}>
      <View style={styles.discoveryStageHeading}>
        <View style={styles.stageCopy}>
          <Text style={styles.sectionTitle}>{title}</Text>
          {description ? <Text style={styles.stageDescription}>{description}</Text> : null}
        </View>
        <View style={styles.stageNumber}>
          <Text style={styles.stageNumberText}>{stage}</Text>
        </View>
      </View>
      {children}
    </View>
  );
}

function DiscoveryPrompt({ message }: { readonly message: string }) {
  return (
    <View style={styles.discoveryPrompt}>
      <Text style={styles.discoveryPromptText}>{message}</Text>
    </View>
  );
}

function QuickFilterChip({
  label,
  onPress,
  selected,
}: {
  readonly label: string;
  readonly onPress: () => void;
  readonly selected: boolean;
}) {
  return (
    <Pressable
      accessibilityLabel={label}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      hitSlop={{ bottom: 6, left: 4, right: 4, top: 6 }}
      onPress={onPress}
      style={({ pressed }: PressableStateCallbackType) => [
        styles.quickFilterChip,
        selected && styles.quickFilterChipSelected,
        pressed && styles.quickFilterChipPressed,
      ]}
    >
      <Text style={[styles.quickFilterLabel, selected && styles.quickFilterLabelSelected]}>{label}</Text>
    </Pressable>
  );
}

function RegionOption({
  category,
  onPress,
  selected,
}: {
  readonly category: { name_en: string; name_fa: string };
  readonly onPress: () => void;
  readonly selected: boolean;
}) {
  return (
    <Pressable
      accessibilityLabel={category.name_fa}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={({ pressed }: PressableStateCallbackType) => [
        styles.regionOption,
        selected && styles.regionOptionSelected,
        pressed && styles.categoryOptionPressed,
      ]}
    >
      <Text style={[styles.regionOptionLabel, selected && styles.regionOptionLabelSelected]}>
        {category.name_fa}
      </Text>
      <Text style={[styles.regionOptionSecondary, selected && styles.regionOptionSecondarySelected]}>
        {category.name_en}
      </Text>
    </Pressable>
  );
}

function MuscleOption({
  category,
  onPress,
  selected,
}: {
  readonly category: { name_en: string; name_fa: string };
  readonly onPress: () => void;
  readonly selected: boolean;
}) {
  return <CategoryOption category={category} kind="muscle" onPress={onPress} selected={selected} />;
}

function FocusOption({
  category,
  label,
  onPress,
  selected,
}: {
  readonly category?: { name_en: string; name_fa: string };
  readonly label?: string;
  readonly onPress: () => void;
  readonly selected: boolean;
}) {
  const option = category ?? { name_en: "", name_fa: label ?? "" };
  return <CategoryOption category={option} kind="focus" onPress={onPress} selected={selected} />;
}

function CategoryOption({
  category,
  kind,
  onPress,
  selected,
}: {
  readonly category: { name_en: string; name_fa: string };
  readonly kind: "focus" | "muscle";
  readonly onPress: () => void;
  readonly selected: boolean;
}) {
  return (
    <Pressable
      accessibilityLabel={category.name_fa}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={({ pressed }: PressableStateCallbackType) => [
        styles.categoryOption,
        kind === "focus" && styles.focusOption,
        selected && styles.categoryOptionSelected,
        pressed && styles.categoryOptionPressed,
      ]}
    >
      <Text style={[styles.categoryOptionLabel, selected && styles.categoryOptionLabelSelected]}>
        {category.name_fa}
      </Text>
      {category.name_en ? (
        <Text style={[styles.categoryOptionSecondary, selected && styles.categoryOptionSecondarySelected]}>
          {category.name_en}
        </Text>
      ) : null}
    </Pressable>
  );
}

function ContentTypeSwitcher({
  onChange,
  value,
}: {
  readonly onChange: (value: ExerciseContentType) => void;
  readonly value: ExerciseContentType;
}) {
  return (
    <SegmentedControl
      accessibilityLabel={exerciseCopy.contentType}
      onChange={(nextValue) => onChange(nextValue as ExerciseContentType)}
      options={[
        { label: exerciseCopy.contentTypes.exercise, value: "exercise" },
        { label: exerciseCopy.contentTypes.guide, value: "guide" },
      ]}
      selectedValue={value}
      testID="catalog-content-type-switcher"
    />
  );
}

function ChoiceRow({ children }: { readonly children: React.ReactNode }) {
  return <View style={styles.choiceRow}>{children}</View>;
}

function ChoiceChip({
  label,
  onPress,
  secondaryLabel,
  selected,
  style,
}: {
  readonly label: string;
  readonly onPress: () => void;
  readonly secondaryLabel?: string;
  readonly selected: boolean;
  readonly style?: StyleProp<ViewStyle>;
}) {
  return (
    <Pressable
      accessibilityLabel={label}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={({ pressed }: PressableStateCallbackType) => [
        styles.chip,
        selected && styles.chipSelected,
        pressed && styles.chipPressed,
        style,
      ]}
    >
      <Text style={[styles.chipLabel, selected && styles.chipLabelSelected]}>{label}</Text>
      {secondaryLabel ? <Text style={styles.chipSecondary}>{secondaryLabel}</Text> : null}
    </Pressable>
  );
}

function ActiveFilterChip({ label, onRemove }: { readonly label: string; readonly onRemove: () => void }) {
  return (
    <View style={styles.activeFilterChip}>
      <Text style={styles.activeFilterText}>{label}</Text>
      <Pressable
        accessibilityLabel={`حذف فیلتر: ${label}`}
        accessibilityRole="button"
        hitSlop={fiticianTokens.spacing[2]}
        onPress={onRemove}
        style={styles.removeFilterButton}
      >
        <Text accessible={false} style={styles.removeFilterGlyph}>×</Text>
      </Pressable>
    </View>
  );
}

function getActiveFilters(
  selection: CatalogSelection,
  categories: ExerciseCategories | undefined,
): ActiveFilter[] {
  const active: ActiveFilter[] = [];
  const search = selection.search.trim();
  if (search) active.push({ key: "search", label: `جست‌وجو: ${search}` });
  if (selection.contentType !== "exercise") {
    active.push({ key: "contentType", label: `نوع محتوا: ${exerciseCopy.contentTypes[selection.contentType]}` });
  }
  if (selection.bodyRegion !== null) {
    active.push({
      key: "bodyRegion",
      label: `ناحیه بدن: ${categories?.body_regions.find((item) => item.value === selection.bodyRegion)?.name_fa ?? exerciseCopy.bodyRegions[selection.bodyRegion]}`,
    });
  }
  if (selection.primaryMuscle !== null) {
    active.push({ key: "primaryMuscle", label: `عضله: ${exerciseCopy.muscles[selection.primaryMuscle]}` });
  }
  if (selection.muscleFocus !== null) {
    active.push({ key: "muscleFocus", label: `تمرکز: ${exerciseCopy.muscleFocuses[selection.muscleFocus]}` });
  }
  if (selection.equipment !== null) {
    active.push({ key: "equipment", label: `تجهیزات: ${exerciseCopy.equipments[selection.equipment]}` });
  }
  if (selection.difficulty !== null) {
    active.push({ key: "difficulty", label: `سختی: ${exerciseCopy.difficulties[selection.difficulty]}` });
  }
  if (selection.exerciseType !== null && selection.exerciseType !== "mobility") {
    active.push({ key: "exerciseType", label: `نوع حرکت: ${exerciseCopy.exerciseTypes[selection.exerciseType]}` });
  }
  return active;
}

function musclesForRegion(categories: ExerciseCategories, region: BodyRegion) {
  if (region === "upper_body") return categories.upper_body;
  if (region === "lower_body") return categories.lower_body;
  return categories.core;
}

function viewData<TData>(state: MobileViewState<TData>): TData | undefined {
  if (state.status === "loading") return undefined;
  return "data" in state ? state.data : undefined;
}

function useConnectivityStatus(): ConnectivityStatus {
  const [status, setStatus] = useState<ConnectivityStatus>(connectivityMonitor.getSnapshot().status);
  useEffect(() => connectivityMonitor.subscribe((snapshot) => setStatus(snapshot.status)), []);
  return status;
}

const equipmentOptions: readonly Equipment[] = [
  "bodyweight",
  "dumbbell",
  "barbell",
  "cable",
  "machine",
  "resistance_band",
  "bench",
  "pull_up_bar",
  "other",
];

const difficultyOptions: readonly Difficulty[] = ["beginner", "intermediate", "advanced"];

const exerciseTypeOptions: readonly ExerciseType[] = [
  "compound",
  "isolation",
  "core",
  "mobility",
  "other",
];

const styles = StyleSheet.create({
  categoryOption: {
    alignItems: "stretch",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flexBasis: "46%",
    flexGrow: 1,
    flexShrink: 1,
    justifyContent: "center",
    minHeight: 56,
    minWidth: 0,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  categoryOptionLabel: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  categoryOptionLabelSelected: {
    color: fiticianTokens.colors.canvas,
  },
  categoryOptionPressed: {
    opacity: 0.82,
  },
  categoryOptionSecondary: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "ltr",
  },
  categoryOptionSecondarySelected: {
    color: fiticianTokens.colors.petrol,
  },
  categoryOptionSelected: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderColor: fiticianTokens.colors.aqua,
  },
  activeFilterChip: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[1],
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingStart: fiticianTokens.spacing[3],
    paddingEnd: fiticianTokens.spacing[2],
  },
  activeFilterRow: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[1],
  },
  activeFilters: {
    gap: fiticianTokens.spacing[1],
  },
  activeFilterText: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  cardCopy: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  cardHeader: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  cardMedia: {
    aspectRatio: 16 / 10,
    borderRadius: fiticianTokens.radii.large,
    overflow: "hidden",
    position: "relative",
    width: "100%",
  },
  cardMediaImage: {
    borderRadius: 0,
    height: "100%",
    minHeight: 0,
    width: "100%",
  },
  cardMediaScrim: {
    backgroundColor: "rgba(2,6,7,0.28)",
    bottom: 0,
    left: 0,
    position: "absolute",
    right: 0,
    top: 0,
  },
  chip: {
    alignItems: "stretch",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    justifyContent: "center",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    minWidth: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  chipLabel: {
    color: fiticianTokens.colors.mist,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  chipLabelSelected: {
    color: fiticianTokens.colors.canvas,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
  },
  chipPressed: {
    opacity: 0.82,
  },
  chipSecondary: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    writingDirection: "ltr",
  },
  chipSelected: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderColor: fiticianTokens.colors.aqua,
  },
  choiceRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[2],
  },
  contentBadge: {
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderRadius: fiticianTokens.radii.pill,
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    overflow: "hidden",
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[1],
    writingDirection: "rtl",
  },
  exerciseCard: {
    gap: fiticianTokens.spacing[3],
  },
  exerciseName: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 30,
    textAlign: "right",
    writingDirection: "rtl",
  },
  exerciseSecondary: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "ltr",
  },
  filterLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  metaRow: {
    alignItems: "flex-start",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  metaText: {
    color: fiticianTokens.colors.muted,
    flexShrink: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  discoveryPanel: {
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.extraLarge,
    borderWidth: 1,
    elevation: fiticianTokens.shadows.soft.elevation,
    gap: fiticianTokens.spacing[4],
    padding: fiticianTokens.spacing[4],
    shadowColor: fiticianTokens.shadows.soft.color,
    shadowOffset: fiticianTokens.shadows.soft.offset,
    shadowOpacity: fiticianTokens.shadows.soft.opacity,
    shadowRadius: fiticianTokens.shadows.soft.radius,
  },
  discoveryPanelFooter: {
    alignItems: "flex-start",
    borderTopColor: fiticianTokens.colors.line,
    borderTopWidth: 1,
    paddingTop: fiticianTokens.spacing[3],
  },
  discoveryPrompt: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    paddingHorizontal: fiticianTokens.spacing[4],
    paddingVertical: fiticianTokens.spacing[3],
  },
  discoveryPromptText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "right",
    writingDirection: "rtl",
  },
  discoveryStage: {
    gap: fiticianTokens.spacing[3],
  },
  discoveryStageHeading: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
  focusOption: {
    minHeight: 48,
  },
  moreFiltersButton: {
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  quickFilterChip: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    justifyContent: "center",
    minHeight: 36,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[1],
  },
  quickFilterChipPressed: {
    opacity: 0.82,
  },
  quickFilterChipSelected: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderColor: fiticianTokens.colors.aqua,
  },
  quickFilterLabel: {
    color: fiticianTokens.colors.mist,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.medium,
    textAlign: "center",
    writingDirection: "rtl",
  },
  quickFilterLabelSelected: {
    color: fiticianTokens.colors.canvas,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
  },
  quickFilterRow: {
    alignItems: "center",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  regionOption: {
    alignItems: "stretch",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flexBasis: 0,
    flexGrow: 1,
    flexShrink: 1,
    justifyContent: "center",
    minHeight: 70,
    minWidth: 0,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  regionOptionLabel: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  regionOptionLabelSelected: {
    color: fiticianTokens.colors.canvas,
  },
  regionOptionRow: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  regionOptionSecondary: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "ltr",
  },
  regionOptionSecondarySelected: {
    color: fiticianTokens.colors.petrol,
  },
  regionOptionSelected: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderColor: fiticianTokens.colors.aqua,
  },
  mediaDifficulty: {
    backgroundColor: fiticianTokens.colors.mediaOverlay,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    bottom: fiticianTokens.spacing[3],
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    overflow: "hidden",
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[1],
    position: "absolute",
    left: fiticianTokens.spacing[3],
    writingDirection: "rtl",
  },
  pageIndicator: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "center",
    writingDirection: "rtl",
  },
  pagination: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    justifyContent: "space-between",
    marginTop: fiticianTokens.spacing[2],
  },
  removeFilterButton: {
    alignItems: "center",
    height: fiticianTokens.layout.minimumTouchTarget,
    justifyContent: "center",
    width: fiticianTokens.layout.minimumTouchTarget,
  },
  removeFilterGlyph: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 24,
  },
  resultCount: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    marginBottom: fiticianTokens.spacing[2],
    textAlign: "right",
    writingDirection: "rtl",
  },
  results: {
    gap: fiticianTokens.spacing[3],
    marginTop: fiticianTokens.spacing[3],
  },
  resultsTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "rtl",
  },
  sectionTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "rtl",
  },
  stageCopy: {
    alignItems: "stretch",
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  stageNumber: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.aquaAtmosphere,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    height: 36,
    justifyContent: "center",
    width: 36,
  },
  stageNumberText: {
    color: fiticianTokens.colors.amber,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    writingDirection: "ltr",
  },
  screen: {
    gap: fiticianTokens.spacing[3],
    paddingBottom: fiticianTokens.spacing[7],
    paddingTop: fiticianTokens.spacing[3],
  },
  sheetActions: {
    gap: fiticianTokens.spacing[2],
    marginTop: fiticianTokens.spacing[2],
  },
  stageDescription: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "right",
    writingDirection: "rtl",
  },
  wrappedOptionRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
});
