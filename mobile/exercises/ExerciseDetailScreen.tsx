import { useQuery } from "@tanstack/react-query";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import {
  StyleSheet,
  Text,
  View,
} from "react-native";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { getMobileRuntimeConfig } from "../config/nativeRuntimeConfig";
import { exerciseKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import { useAndroidBackHandler } from "../ui/navigation/BackBehaviorProvider";
import {
  Button,
  Card,
  DisclosureCard,
  EmptyState,
  Notice,
  Skeleton,
} from "../ui/components";
import { getMobileViewState } from "../ui/requestState";
import { Screen } from "../ui/layout";
import { languageForDirection, type MobileLanguage } from "../ui/rtl";
import { fiticianTokens } from "../ui/tokens";
import {
  createExerciseApi,
  type ExerciseDetail,
} from "./exerciseApi";
import { ExerciseMediaCarousel } from "./ExerciseMediaCarousel";
import { GenderMediaSelector } from "./GenderMediaSelector";
import {
  availableMediaPresentations,
  buildExerciseMediaItems,
  type ExerciseMediaItem,
  type GenderMediaPresentation,
} from "./exerciseMedia";
import { exerciseCopy, exerciseTitle } from "./exerciseCopy";

type MediaPresentationChoice = GenderMediaPresentation;

const detailCopy = {
  en: {
    back: "Back",
    bodyRegion: "Body region",
    details: "Exercise details",
    difficulty: "Difficulty",
    equipment: "Equipment",
    error: "Could not load exercise details.",
    focus: "Muscle focus",
    instructions: "Instructions",
    library: "Exercise library",
    noInformation: "No information recorded.",
    retry: "Try again",
    secondaryMuscles: "Secondary muscles",
    safety: "Safety",
    targetMuscle: "Target muscle",
    guide: "Exercise guide",
    unknownExercise: "Exercise not found",
    unavailable: "Not available",
  },
  fa: {
    back: "بازگشت",
    bodyRegion: "ناحیه بدن",
    details: "مشخصات حرکت",
    difficulty: exerciseCopy.difficulty,
    equipment: exerciseCopy.equipment,
    error: exerciseCopy.error,
    focus: exerciseCopy.focus,
    instructions: exerciseCopy.instructions,
    library: exerciseCopy.library,
    noInformation: "اطلاعاتی ثبت نشده است.",
    retry: exerciseCopy.retry,
    secondaryMuscles: exerciseCopy.secondaryMuscles,
    safety: exerciseCopy.safety,
    targetMuscle: "عضله هدف",
    guide: "راهنمای حرکت",
    unknownExercise: exerciseCopy.unknownExercise,
    unavailable: "بررسی نشده",
  },
} as const;

const englishExerciseValues: Readonly<Record<string, string>> = {
  abs: "Abs",
  abductors: "Abductors",
  adductors: "Adductors",
  adductor_mobility: "Adductor mobility",
  anti_extension: "Anti-extension",
  anti_rotation: "Anti-rotation",
  advanced: "Advanced",
  back: "Back",
  barbell: "Barbell",
  beginner: "Beginner",
  bench: "Bench",
  biceps: "Biceps",
  biceps_brachii: "Biceps brachii",
  brachialis_brachioradialis: "Brachialis and brachioradialis",
  bodyweight: "Bodyweight",
  cable: "Cable",
  calves: "Calves",
  chest: "Chest",
  compound: "Compound",
  core: "Core",
  dumbbell: "Dumbbell",
  forearm_extensors: "Forearm extensors",
  forearm_flexors: "Forearm flexors",
  forearms: "Forearms",
  front_delt: "Front deltoid",
  general_back: "General back",
  general_biceps: "General biceps",
  general_calves: "General calves",
  general_chest: "General chest",
  general_forearms: "General forearms",
  general_quadriceps: "General quadriceps",
  general_shoulders: "General shoulders",
  general_triceps: "General triceps",
  gastrocnemius: "Gastrocnemius",
  glutes: "Glutes",
  glute_max: "Gluteus maximus",
  glute_medius_minimus: "Gluteus medius and minimus",
  hamstrings: "Hamstrings",
  hamstrings_hip_extension: "Hamstring hip extension",
  hamstrings_knee_flexion: "Hamstring knee flexion",
  hip_adduction: "Hip adduction",
  hip_flexion_posterior_tilt: "Hip flexion and posterior tilt",
  intermediate: "Intermediate",
  isolation: "Isolation",
  lateral_delt: "Lateral deltoid",
  lateral_flexion: "Lateral flexion",
  legs: "Legs",
  lats: "Lats",
  lower_chest: "Lower chest",
  lower_back: "Lower back",
  lower_body: "Lower body",
  lumbar_erectors: "Lumbar erectors",
  machine: "Machine",
  mid_back_rhomboids: "Mid-back and rhomboids",
  mid_chest: "Mid chest",
  mid_lower_traps: "Mid and lower traps",
  neck: "Neck",
  neck_flexion: "Neck flexion",
  neck_lateral_extension: "Neck lateral extension",
  obliques: "Obliques",
  other: "Other",
  pull_up_bar: "Pull-up bar",
  quadriceps: "Quadriceps",
  rear_delt: "Rear deltoid",
  resistance_band: "Resistance band",
  rectus_femoris: "Rectus femoris",
  shoulders: "Shoulders",
  soleus: "Soleus",
  thoracic_mobility: "Thoracic mobility",
  traps: "Traps",
  trunk_flexion: "Trunk flexion",
  trunk_rotation: "Trunk rotation",
  triceps: "Triceps",
  triceps_lateral_medial_heads: "Lateral and medial triceps heads",
  triceps_long_head: "Long head of triceps",
  upper_body: "Upper body",
  upper_back: "Upper back",
  upper_chest: "Upper chest",
  upper_traps: "Upper traps",
  vasti: "Vasti",
};

export function ExerciseDetailScreen() {
  const auth = useMobileAuth();
  const router = useRouter();
  const params = useLocalSearchParams<{ slug?: string | string[] }>();
  const slug = Array.isArray(params.slug) ? params.slug[0] : params.slug;
  const api = useMemo(() => createExerciseApi(auth.request), [auth.request]);
  const runtime = useMemo(() => getMobileRuntimeConfig(), []);
  const connectivityStatus = useConnectivityStatus();
  const language = languageForDirection();
  const [presentation, setPresentation] = useState<MediaPresentationChoice | null>(null);
  const [mediaIndex, setMediaIndex] = useState(0);
  const presentationQuery = presentation ?? undefined;
  const detailQuery = useQuery({
    enabled: slug !== undefined,
    queryFn: () => api.get(slug ?? "", presentationQuery),
    queryKey: [
      ...exerciseKeys.detail(slug ?? ""),
      presentationQuery ?? "profile",
    ],
  });
  const mediaInventoryQuery = useQuery({
    enabled: slug !== undefined,
    queryFn: () => api.get(slug ?? "", "unspecified"),
    queryKey: [...exerciseKeys.detail(slug ?? ""), "media-inventory"],
  });
  const detailState = getMobileViewState(detailQuery, { connectivityStatus });
  const detail = viewData(detailState);
  const mediaItems = useMemo(
    () => (detail === undefined || detail === null ? [] : buildExerciseMediaItems(detail)),
    [detail],
  );
  const mediaInventoryItems = useMemo(() => {
    const inventory = mediaInventoryQuery.data ?? detail;
    return inventory === undefined || inventory === null ? [] : buildExerciseMediaItems(inventory);
  }, [detail, mediaInventoryQuery.data]);
  const availablePresentations = useMemo(
    () => availableMediaPresentations(mediaInventoryItems.length > 0 ? mediaInventoryItems : mediaItems),
    [mediaInventoryItems, mediaItems],
  );
  const resolvedPresentation = presentation ?? resolveMediaPresentation(detail);
  const effectivePresentation = availablePresentations.includes(resolvedPresentation)
    ? resolvedPresentation
    : availablePresentations[0] ?? resolvedPresentation;
  const mediaItemKeys = mediaItems.map((item) => item.key).join("\u001f");

  useEffect(() => {
    setPresentation(null);
    setMediaIndex(0);
  }, [slug]);

  useEffect(() => {
    setMediaIndex(0);
  }, [detail?.slug, mediaItemKeys, presentationQuery]);

  useEffect(() => {
    if (
      detail !== undefined &&
      detail !== null &&
      presentation !== null &&
      resolveMediaPresentation(detail) !== presentation
    ) {
      setPresentation(resolveMediaPresentation(detail));
    }
  }, [detail, presentation]);

  useAndroidBackHandler("wizard", () => {
    router.back();
    return true;
  }, true);

  function choosePresentation(next: MediaPresentationChoice) {
    if (next === effectivePresentation || !availablePresentations.includes(next)) return;
    setPresentation(next);
    setMediaIndex(0);
  }

  if (slug === undefined) {
    return (
      <Screen contentWidth="reading">
        <EmptyState title={detailCopy[language].unknownExercise} actionLabel={detailCopy[language].back} onAction={() => router.back()} />
      </Screen>
    );
  }

  return (
    <Screen contentWidth="reading" contentContainerStyle={styles.screen}>
      <View
        style={[styles.breadcrumbRow, language === "en" && styles.breadcrumbRowEnglish]}
        testID="exercise-detail-breadcrumb"
      >
        <View style={[styles.breadcrumbCopy, language === "en" && styles.breadcrumbCopyEnglish]}>
          <Text style={[styles.breadcrumbLabel, language === "en" && styles.breadcrumbLabelEnglish]}>
            {detailCopy[language].library}
          </Text>
          <Text style={[styles.breadcrumbCurrent, language === "en" && styles.breadcrumbCurrentEnglish]}>
            {detailCopy[language].guide}
          </Text>
        </View>
        <Button
          label={detailCopy[language].back}
          onPress={() => router.back()}
          style={styles.backButton}
          variant="ghost"
        />
      </View>

      {detailState.status === "loading" ? <DetailSkeleton /> : null}
      {detailState.status === "error" ? (
        <Notice
          actionLabel={detailCopy[language].retry}
          message={detailCopy[language].error}
          onAction={() => void detailQuery.refetch()}
          variant="danger"
        />
      ) : null}
      {detailState.status === "offline" && detail === undefined ? (
        <Notice
          message={language === "en" ? "Connect to the internet to load exercise details." : "برای دریافت جزئیات حرکت به اینترنت وصل شو."}
          variant="offline"
        />
      ) : null}
      {detail === null ? (
        <EmptyState title={detailCopy[language].unknownExercise} actionLabel={detailCopy[language].back} onAction={() => router.back()} />
      ) : null}
      {detail !== undefined && detail !== null ? (
        <>
          {detailState.status === "offline" ? (
            <Notice
              message={language === "en" ? "Showing saved exercise details; the internet is unavailable." : "نمایش جزئیات ذخیره‌شده؛ اتصال اینترنت برقرار نیست."}
              variant="offline"
            />
          ) : null}
          <ExerciseMediaPanel
            availablePresentations={availablePresentations}
            detail={detail}
            effectivePresentation={effectivePresentation}
            language={language}
            mediaIndex={mediaIndex}
            mediaItems={mediaItems}
            onMediaIndexChange={setMediaIndex}
            onPresentationChange={choosePresentation}
            runtimeApiBaseUrl={runtime.apiBaseUrl}
          />
          <ExerciseInformation detail={detail} language={language} />
        </>
      ) : null}
    </Screen>
  );
}

function ExerciseMediaPanel({
  availablePresentations,
  detail,
  effectivePresentation,
  language,
  mediaIndex,
  mediaItems,
  onMediaIndexChange,
  onPresentationChange,
  runtimeApiBaseUrl,
}: {
  readonly availablePresentations: readonly MediaPresentationChoice[];
  readonly detail: ExerciseDetail;
  readonly effectivePresentation: MediaPresentationChoice;
  readonly language: ReturnType<typeof languageForDirection>;
  readonly mediaIndex: number;
  readonly mediaItems: ExerciseMediaItem[];
  readonly onMediaIndexChange: (index: number) => void;
  readonly onPresentationChange: (presentation: MediaPresentationChoice) => void;
  readonly runtimeApiBaseUrl: string;
}) {
  const name = exerciseTitle(detail.name_fa, detail.name_en, language);
  return (
    <Card style={[styles.mediaCard, language === "en" && styles.mediaCardEnglish]} variant="hero">
      <ExerciseMediaCarousel
        apiBaseUrl={runtimeApiBaseUrl}
        items={mediaItems}
        language={language}
        name={name}
        onIndexChange={onMediaIndexChange}
        selectedIndex={mediaIndex}
      />
      <View style={styles.mediaFooter}>
        <GenderMediaSelector
          available={availablePresentations}
          language={language}
          onChange={onPresentationChange}
          selected={effectivePresentation}
        />
        <Text
          style={[styles.mediaTitle, language === "en" && styles.mediaTitleEnglish]}
          testID="exercise-media-card-title"
        >
          {name}
        </Text>
      </View>
    </Card>
  );
}

function ExerciseInformation({ detail, language }: { readonly detail: ExerciseDetail; readonly language: MobileLanguage }) {
  const copy = detailCopy[language];
  const instructions = language === "en" && detail.instructions_en.length > 0
    ? detail.instructions_en
    : detail.instructions_fa.length > 0 ? detail.instructions_fa : detail.instructions_en;
  const safetyNotes = language === "en" && detail.safety_notes_en.length > 0
    ? detail.safety_notes_en
    : detail.safety_notes_fa.length > 0 ? detail.safety_notes_fa : detail.safety_notes_en;
  return (
    <View style={styles.information}>
      <DisclosureCard direction={language === "en" ? "ltr" : "rtl"} title={copy.details} icon="training" style={styles.infoCard}>
        <InfoRow
          label={copy.bodyRegion}
          language={language}
          value={detail.body_region === null ? copy.unavailable : localizedValue(language, detail.body_region, exerciseCopy.bodyRegions)}
        />
        <InfoRow
          label={copy.targetMuscle}
          language={language}
          value={detail.primary_muscle === null ? copy.unavailable : localizedValue(language, detail.primary_muscle, exerciseCopy.muscles)}
        />
        {detail.muscle_focus !== null && detail.muscle_focus !== undefined ? (
          <InfoRow
            label={copy.focus}
            language={language}
            value={localizedValue(language, detail.muscle_focus, exerciseCopy.muscleFocuses)}
          />
        ) : null}
        <InfoRow
          label={copy.difficulty}
          language={language}
          value={localizedValue(language, detail.difficulty, exerciseCopy.difficulties)}
        />
        <InfoRow
          label={copy.equipment}
          language={language}
          value={detail.equipment.map((value) => localizedValue(language, value, exerciseCopy.equipments)).join(language === "en" ? ", " : "، ") || "—"}
        />
        <InfoRow
          label={copy.secondaryMuscles}
          language={language}
          value={detail.secondary_muscles.map((value) => localizedValue(language, value, exerciseCopy.muscles)).join(language === "en" ? ", " : "، ") || "—"}
        />
      </DisclosureCard>
      <InstructionList items={instructions} language={language} title={copy.instructions} />
      <InstructionList items={safetyNotes} language={language} title={copy.safety} warning />
    </View>
  );
}

function InstructionList({
  items,
  language,
  title,
  warning = false,
}: {
  readonly items: string[];
  readonly language: MobileLanguage;
  readonly title: string;
  readonly warning?: boolean;
}) {
  const isEnglish = language === "en";
  return (
    <DisclosureCard
      direction={language === "en" ? "ltr" : "rtl"}
      title={title}
      icon={warning ? "shield" : "play"}
      summary={`${items.length.toLocaleString(isEnglish ? "en-US" : "fa-IR")} ${isEnglish ? "items" : "نکته"}`}
      style={[styles.infoCard, warning && styles.warningCard]}
    >
      {items.length > 0 ? items.map((item, index) => (
        <View key={`${index}-${item}`} style={[styles.instructionRow, isEnglish && styles.instructionRowEnglish]}>
          <Text style={[styles.instructionNumber, isEnglish && styles.instructionNumberEnglish]}>{index + 1}</Text>
          <Text style={[styles.instructionText, isEnglish && styles.instructionTextEnglish]}>{item}</Text>
        </View>
      )) : <Text style={[styles.mutedText, isEnglish && styles.mutedTextEnglish]}>{isEnglish ? detailCopy.en.noInformation : detailCopy.fa.noInformation}</Text>}
    </DisclosureCard>
  );
}

function InfoRow({ label, language, value }: { readonly label: string; readonly language: MobileLanguage; readonly value: string }) {
  return (
    <View style={[styles.infoRow, language === "en" && styles.infoRowEnglish]}>
      {language === "en" ? (
        <>
          <Text style={[styles.infoLabel, styles.infoLabelEnglish]}>{label}</Text>
          <Text style={[styles.infoValue, styles.infoValueEnglish]}>{value}</Text>
        </>
      ) : (
        <>
          <Text style={styles.infoValue}>{value}</Text>
          <Text style={styles.infoLabel}>{label}</Text>
        </>
      )}
    </View>
  );
}

function DetailSkeleton() {
  return (
    <View style={styles.skeletonGroup}>
      <Skeleton height={232} />
      <Skeleton height={130} />
      <Skeleton height={180} />
    </View>
  );
}

function localizedValue<T extends string>(
  language: MobileLanguage,
  value: T,
  persianValues: Readonly<Record<T, string>>,
): string {
  if (language === "en") return englishExerciseValues[value] ?? detailCopy.en.unavailable;
  return persianValues[value] ?? detailCopy.fa.unavailable;
}

function resolveMediaPresentation(detail: ExerciseDetail | null | undefined): MediaPresentationChoice {
  if (detail?.media_presentation === "female") return "female";
  if (detail?.media_presentation === "male") return "male";
  return detail?.media_assets?.[0]?.presentation === "female" ? "female" : "male";
}

function viewData<TData>(state: ReturnType<typeof getMobileViewState<TData>>): TData | undefined {
  if (state.status === "loading") return undefined;
  return "data" in state ? state.data : undefined;
}

function useConnectivityStatus(): ConnectivityStatus {
  const [status, setStatus] = useState<ConnectivityStatus>(connectivityMonitor.getSnapshot().status);
  useEffect(() => connectivityMonitor.subscribe((snapshot) => setStatus(snapshot.status)), []);
  return status;
}

const styles = StyleSheet.create({
  backButton: {
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[3],
  },
  breadcrumbCopy: {
    alignItems: "flex-end",
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
  },
  breadcrumbCopyEnglish: {
    alignItems: "flex-start",
  },
  breadcrumbCurrent: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  breadcrumbCurrentEnglish: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    textAlign: "left",
    writingDirection: "ltr",
  },
  breadcrumbLabel: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  breadcrumbLabelEnglish: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    textAlign: "left",
    writingDirection: "ltr",
  },
  breadcrumbRow: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    width: "100%",
  },
  breadcrumbRowEnglish: {
    direction: "ltr",
    flexDirection: "row",
  },
  infoCard: {
    gap: fiticianTokens.spacing[3],
    marginBottom: fiticianTokens.spacing[4],
  },
  infoLabel: {
    color: fiticianTokens.colors.muted,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  infoLabelEnglish: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    textAlign: "left",
    writingDirection: "ltr",
  },
  information: {
    marginTop: fiticianTokens.spacing[4],
  },
  infoRow: {
    alignItems: "center",
    borderBottomColor: fiticianTokens.colors.line,
    borderBottomWidth: 1,
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  infoRowEnglish: {
    direction: "ltr",
    flexDirection: "row",
  },
  infoValue: {
    color: fiticianTokens.colors.ink,
    flex: 2,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  infoValueEnglish: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    textAlign: "left",
    writingDirection: "ltr",
  },
  instructionNumber: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    color: fiticianTokens.colors.canvas,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    minWidth: 24,
    padding: fiticianTokens.spacing[1],
    textAlign: "center",
  },
  instructionNumberEnglish: {
    writingDirection: "ltr",
  },
  instructionRow: {
    alignItems: "flex-start",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
  },
  instructionRowEnglish: {
    direction: "ltr",
    flexDirection: "row",
  },
  instructionText: {
    color: fiticianTokens.colors.ink,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 27,
    textAlign: "right",
    writingDirection: "rtl",
  },
  instructionTextEnglish: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    textAlign: "left",
    writingDirection: "ltr",
  },
  mediaCard: {
    overflow: "hidden",
    padding: 0,
  },
  mediaCardEnglish: {
    direction: "ltr",
  },
  mediaFooter: {
    alignItems: "stretch",
    gap: fiticianTokens.spacing[2],
    paddingHorizontal: fiticianTokens.spacing[4],
    paddingVertical: fiticianTokens.spacing[3],
  },
  mediaTitle: {
    alignSelf: "stretch",
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h2,
    lineHeight: 32,
    textAlign: "center",
    writingDirection: "rtl",
  },
  mediaTitleEnglish: {
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    writingDirection: "ltr",
  },
  mutedText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    textAlign: "right",
    writingDirection: "rtl",
  },
  mutedTextEnglish: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    textAlign: "left",
    writingDirection: "ltr",
  },
  screen: {
    gap: fiticianTokens.spacing[3],
    paddingBottom: fiticianTokens.spacing[7],
    paddingTop: fiticianTokens.spacing[3],
  },
  skeletonGroup: {
    gap: fiticianTokens.spacing[3],
  },
  warningCard: {
    borderColor: fiticianTokens.colors.amber,
  },
});
