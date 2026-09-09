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
import { Button, Card, EmptyState, Notice, Skeleton, TextField } from "../ui/components";
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
  const canLoadExercises =
    selection.primaryMuscle !== null ||
    selection.label !== null ||
    selection.exerciseType !== null;
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
    updateSelection({ muscleFocus: null, primaryMuscle });
  }

  function chooseSpecialFilter(changes: Pick<CatalogSelection, "exerciseType" | "label">) {
    updateSelection({
      ...changes,
      bodyRegion: null,
      muscleFocus: null,
      primaryMuscle: null,
    });
  }

  function clearFilters() {
    setSelection(initialSelection);
    setPage(1);
  }

  function openExercise(exercise: ExerciseSummary) {
    router.push({ pathname: "/member/exercises/[slug]", params: { slug: exercise.slug } });
  }

  return (
    <Screen contentWidth="reading">
      <View style={styles.header}>
        <Text style={styles.brand}>FITICIAN</Text>
        <Text accessibilityRole="header" style={styles.title}>{exerciseCopy.library}</Text>
        <Text style={styles.intro}>{exerciseCopy.catalogIntro}</Text>
      </View>

      <View style={styles.actions}>
        <Button label={exerciseCopy.clearFilters} onPress={clearFilters} variant="ghost" />
      </View>

      <Card style={styles.filterCard}>
        <Text style={styles.sectionTitle}>{exerciseCopy.specialFilters}</Text>
        <ChoiceRow>
          <ChoiceChip
            label={exerciseCopy.fullBody}
            selected={selection.label === "full_body"}
            onPress={() => chooseSpecialFilter({ exerciseType: null, label: "full_body" })}
          />
          <ChoiceChip
            label={exerciseCopy.labels.cardio}
            selected={selection.label === "cardio"}
            onPress={() => chooseSpecialFilter({ exerciseType: null, label: "cardio" })}
          />
          <ChoiceChip
            label={exerciseCopy.mobility}
            selected={selection.exerciseType === "mobility"}
            onPress={() => chooseSpecialFilter({ exerciseType: "mobility", label: null })}
          />
        </ChoiceRow>
      </Card>

      <Card style={styles.filterCard}>
        <Text style={styles.sectionTitle}>{exerciseCopy.contentType}</Text>
        <ChoiceRow>
          <ChoiceChip
            label={exerciseCopy.contentTypes.exercise}
            selected={selection.contentType === "exercise"}
            onPress={() => updateSelection({ contentType: "exercise", muscleFocus: null })}
          />
          <ChoiceChip
            label={exerciseCopy.contentTypes.guide}
            selected={selection.contentType === "guide"}
            onPress={() => updateSelection({ contentType: "guide", muscleFocus: null })}
          />
        </ChoiceRow>
      </Card>

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
          <FilterStage title={exerciseCopy.bodyRegion} description={exerciseCopy.bodyRegionIntro}>
            <ChoiceRow>
              {categories.body_regions.map((category) => (
                <ChoiceChip
                  key={category.value}
                  label={category.name_fa}
                  secondaryLabel={category.name_en}
                  selected={selection.bodyRegion === category.value}
                  onPress={() => chooseBodyRegion(category.value)}
                />
              ))}
            </ChoiceRow>
          </FilterStage>

          {selection.bodyRegion !== null ? (
            <FilterStage title={exerciseCopy.muscle} description={exerciseCopy.muscleIntro}>
              <ChoiceRow>
                {availableMuscles.map((category) => (
                  <ChoiceChip
                    key={category.value}
                    label={category.name_fa}
                    secondaryLabel={category.name_en}
                    selected={selection.primaryMuscle === category.value}
                    onPress={() => chooseMuscle(category.value)}
                  />
                ))}
              </ChoiceRow>
            </FilterStage>
          ) : null}

          {selection.primaryMuscle !== null && selection.contentType === "exercise" ? (
            <FilterStage title={exerciseCopy.focus}>
              <ChoiceRow>
                <ChoiceChip
                  label="همه تمرکزها"
                  selected={selection.muscleFocus === null}
                  onPress={() => updateSelection({ muscleFocus: null })}
                />
                {availableFocuses.map((category) => (
                  <ChoiceChip
                    key={category.value}
                    label={category.name_fa}
                    secondaryLabel={category.name_en}
                    selected={selection.muscleFocus === category.value}
                    onPress={() => updateSelection({ muscleFocus: category.value })}
                  />
                ))}
              </ChoiceRow>
            </FilterStage>
          ) : null}
        </>
      ) : null}

      <Card style={styles.filterCard}>
        <Text style={styles.sectionTitle}>{exerciseCopy.filters}</Text>
        <TextField
          accessibilityLabel={exerciseCopy.search}
          label={exerciseCopy.search}
          onChangeText={(search) => updateSelection({ search })}
          placeholder="مثلاً پرس سینه"
          returnKeyType="search"
          value={selection.search}
        />
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
      </Card>

      <ExerciseResults
        canLoad={canLoadExercises}
        page={exercisePage}
        state={exercisesState}
        onOpen={openExercise}
        onPageChange={setPage}
        onRetry={() => void exercisesQuery.refetch()}
      />
    </Screen>
  );
}

function ExerciseResults({
  canLoad,
  onOpen,
  onPageChange,
  onRetry,
  page,
  state,
}: {
  readonly canLoad: boolean;
  readonly onOpen: (exercise: ExerciseSummary) => void;
  readonly onPageChange: (page: number) => void;
  readonly onRetry: () => void;
  readonly page: PaginatedExercises | undefined;
  readonly state: MobileViewState<PaginatedExercises>;
}) {
  if (!canLoad) {
    return <Notice message={exerciseCopy.noSelection} variant="info" />;
  }
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

function FilterStage({
  children,
  description,
  title,
}: {
  readonly children: React.ReactNode;
  readonly description?: string;
  readonly title: string;
}) {
  return (
    <View style={styles.stage}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {description ? <Text style={styles.stageDescription}>{description}</Text> : null}
      {children}
    </View>
  );
}

function ChoiceRow({ children }: { readonly children: React.ReactNode }) {
  return (
    <ScrollView
      contentContainerStyle={styles.choiceRow}
      horizontal
      showsHorizontalScrollIndicator={false}
    >
      {children}
    </ScrollView>
  );
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
  actions: {
    alignItems: "flex-start",
    marginBottom: fiticianTokens.spacing[3],
  },
  brand: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    letterSpacing: 1.4,
    textAlign: "left",
    writingDirection: "ltr",
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
    borderRadius: fiticianTokens.radii.large,
    height: 188,
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
    alignItems: "flex-end",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    justifyContent: "center",
    marginEnd: fiticianTokens.spacing[2],
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
    flexDirection: "row-reverse",
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
  filterCard: {
    gap: fiticianTokens.spacing[3],
    marginBottom: fiticianTokens.spacing[4],
  },
  filterLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  header: {
    gap: fiticianTokens.spacing[2],
    marginBottom: fiticianTokens.spacing[4],
  },
  intro: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 27,
    textAlign: "right",
    writingDirection: "rtl",
  },
  metaRow: {
    alignItems: "flex-start",
    flexDirection: "row-reverse",
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
  mediaDifficulty: {
    backgroundColor: "rgba(2,6,7,0.74)",
    borderColor: "rgba(80,223,206,0.28)",
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
    right: fiticianTokens.spacing[3],
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
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[2],
    justifyContent: "space-between",
    marginTop: fiticianTokens.spacing[2],
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
  sectionTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "rtl",
  },
  stage: {
    gap: fiticianTokens.spacing[2],
    marginBottom: fiticianTokens.spacing[4],
  },
  stageDescription: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "right",
    writingDirection: "rtl",
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 40,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
