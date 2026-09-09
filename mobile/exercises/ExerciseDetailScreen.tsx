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
  EmptyState,
  Notice,
  ScreenHeader,
  Skeleton,
} from "../ui/components";
import { getMobileViewState } from "../ui/requestState";
import { Screen } from "../ui/layout";
import { languageForDirection } from "../ui/rtl";
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
        <EmptyState title={exerciseCopy.unknownExercise} actionLabel="بازگشت" onAction={() => router.back()} />
      </Screen>
    );
  }

  return (
    <Screen contentWidth="reading" contentContainerStyle={styles.screen}>
      <ScreenHeader
        action={<Button label="بازگشت" onPress={() => router.back()} style={styles.backButton} variant="ghost" />}
        compact
        eyebrow={exerciseCopy.library}
        subtitle="رسانه، مشخصات و نکات اجرای ایمن"
        title={detail === undefined || detail === null ? "راهنمای حرکت" : exerciseTitle(detail.name_fa, detail.name_en)}
      />

      {detailState.status === "loading" ? <DetailSkeleton /> : null}
      {detailState.status === "error" ? (
        <Notice
          actionLabel={exerciseCopy.retry}
          message={exerciseCopy.error}
          onAction={() => void detailQuery.refetch()}
          variant="danger"
        />
      ) : null}
      {detailState.status === "offline" && detail === undefined ? (
        <Notice message="برای دریافت جزئیات حرکت به اینترنت وصل شو." variant="offline" />
      ) : null}
      {detail === null ? (
        <EmptyState title={exerciseCopy.unknownExercise} actionLabel="بازگشت" onAction={() => router.back()} />
      ) : null}
      {detail !== undefined && detail !== null ? (
        <>
          {detailState.status === "offline" ? (
            <Notice message="نمایش جزئیات ذخیره‌شده؛ اتصال اینترنت برقرار نیست." variant="offline" />
          ) : detailState.status === "stale" ? (
            <Notice message={exerciseCopy.stale} variant="info" />
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
          <ExerciseInformation detail={detail} />
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
      <View style={[styles.mediaFooter, language === "en" && styles.mediaFooterEnglish]}>
        <Text
          style={[styles.mediaTitle, language === "en" && styles.mediaTitleEnglish]}
          testID="exercise-media-card-title"
        >
          {name}
        </Text>
        <GenderMediaSelector
          available={availablePresentations}
          language={language}
          onChange={onPresentationChange}
          selected={effectivePresentation}
        />
      </View>
    </Card>
  );
}

function ExerciseInformation({ detail }: { readonly detail: ExerciseDetail }) {
  const instructions = detail.instructions_fa.length > 0
    ? detail.instructions_fa
    : detail.instructions_en;
  const safetyNotes = detail.safety_notes_fa.length > 0
    ? detail.safety_notes_fa
    : detail.safety_notes_en;
  return (
    <View style={styles.information}>
      <Card style={styles.infoCard}>
        <Text style={styles.sectionTitle}>مشخصات حرکت</Text>
        <InfoRow
          label="ناحیه بدن"
          value={detail.body_region === null ? "بررسی نشده" : exerciseCopy.bodyRegions[detail.body_region]}
        />
        <InfoRow
          label="عضله هدف"
          value={detail.primary_muscle === null ? "بررسی نشده" : exerciseCopy.muscles[detail.primary_muscle]}
        />
        {detail.muscle_focus !== null && detail.muscle_focus !== undefined ? (
          <InfoRow label={exerciseCopy.focus} value={exerciseCopy.muscleFocuses[detail.muscle_focus]} />
        ) : null}
        <InfoRow label={exerciseCopy.difficulty} value={exerciseCopy.difficulties[detail.difficulty]} />
        <InfoRow
          label={exerciseCopy.equipment}
          value={detail.equipment.map((value) => exerciseCopy.equipments[value]).join("، ") || "—"}
        />
        <InfoRow
          label={exerciseCopy.secondaryMuscles}
          value={detail.secondary_muscles.map((value) => exerciseCopy.muscles[value]).join("، ") || "—"}
        />
      </Card>
      <InstructionList items={instructions} title={exerciseCopy.instructions} />
      <InstructionList items={safetyNotes} title={exerciseCopy.safety} warning />
    </View>
  );
}

function InstructionList({
  items,
  title,
  warning = false,
}: {
  readonly items: string[];
  readonly title: string;
  readonly warning?: boolean;
}) {
  return (
    <Card style={[styles.infoCard, warning && styles.warningCard]}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {items.length > 0 ? items.map((item, index) => (
        <View key={`${index}-${item}`} style={styles.instructionRow}>
          <Text style={styles.instructionNumber}>{index + 1}</Text>
          <Text style={styles.instructionText}>{item}</Text>
        </View>
      )) : <Text style={styles.mutedText}>اطلاعاتی ثبت نشده است.</Text>}
    </Card>
  );
}

function InfoRow({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoValue}>{value}</Text>
      <Text style={styles.infoLabel}>{label}</Text>
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
  infoValue: {
    color: fiticianTokens.colors.ink,
    flex: 2,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
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
  instructionRow: {
    alignItems: "flex-start",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
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
  mediaCard: {
    overflow: "hidden",
    padding: 0,
  },
  mediaCardEnglish: {
    direction: "ltr",
  },
  mediaFooter: {
    alignItems: "flex-end",
    gap: fiticianTokens.spacing[2],
    paddingHorizontal: fiticianTokens.spacing[4],
    paddingVertical: fiticianTokens.spacing[3],
  },
  mediaFooterEnglish: {
    alignItems: "flex-start",
  },
  mediaTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h2,
    lineHeight: 32,
    textAlign: "right",
    writingDirection: "rtl",
  },
  mediaTitleEnglish: {
    fontFamily: fiticianTokens.typography.fontFamily.displayEnglish,
    textAlign: "left",
    writingDirection: "ltr",
  },
  mutedText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
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
  backButton: {
    minHeight: 42,
    paddingHorizontal: fiticianTokens.spacing[3],
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
