import { useQuery } from "@tanstack/react-query";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { getMobileRuntimeConfig } from "../config/nativeRuntimeConfig";
import { exerciseKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import { useAndroidBackHandler } from "../ui/navigation/BackBehaviorProvider";
import { Button, Card, EmptyState, Notice, Skeleton, Media } from "../ui/components";
import { getMobileViewState } from "../ui/requestState";
import { Screen } from "../ui/layout";
import { fiticianTokens } from "../ui/tokens";
import {
  createExerciseApi,
  type ExerciseDetail,
} from "./exerciseApi";
import {
  buildExerciseMediaItems,
  resolveExerciseMediaUrl,
  type ExerciseMediaItem,
} from "./exerciseMedia";
import {
  exerciseCopy,
  exerciseSecondaryTitle,
  exerciseTitle,
} from "./exerciseCopy";

type MediaPresentationChoice = "male" | "female";

export function ExerciseDetailScreen() {
  const auth = useMobileAuth();
  const router = useRouter();
  const params = useLocalSearchParams<{ slug?: string | string[] }>();
  const slug = Array.isArray(params.slug) ? params.slug[0] : params.slug;
  const api = useMemo(() => createExerciseApi(auth.request), [auth.request]);
  const runtime = useMemo(() => getMobileRuntimeConfig(), []);
  const connectivityStatus = useConnectivityStatus();
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
  const detailState = getMobileViewState(detailQuery, { connectivityStatus });
  const detail = viewData(detailState);
  const mediaItems = useMemo(
    () => (detail === undefined || detail === null ? [] : buildExerciseMediaItems(detail)),
    [detail],
  );
  const selectedItem = mediaItems[mediaIndex] ?? mediaItems[0];
  const effectivePresentation = presentation ?? resolveMediaPresentation(detail);

  useEffect(() => {
    setMediaIndex(0);
  }, [detail?.slug, presentationQuery, mediaItems.length]);

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
    if (next !== effectivePresentation) {
      setPresentation(next);
      setMediaIndex(0);
    }
  }

  if (slug === undefined) {
    return (
      <Screen contentWidth="reading">
        <EmptyState title={exerciseCopy.unknownExercise} actionLabel="بازگشت" onAction={() => router.back()} />
      </Screen>
    );
  }

  return (
    <Screen contentWidth="reading">
      <View style={styles.header}>
        <Button label="بازگشت" onPress={() => router.back()} variant="ghost" />
        <Text style={styles.eyebrow}>{exerciseCopy.library}</Text>
      </View>

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
            detail={detail}
            effectivePresentation={effectivePresentation}
            mediaIndex={mediaIndex}
            mediaItems={mediaItems}
            runtimeApiBaseUrl={runtime.apiBaseUrl}
            selectedItem={selectedItem}
            onMediaIndexChange={setMediaIndex}
            onPresentationChange={choosePresentation}
          />
          <ExerciseInformation detail={detail} />
        </>
      ) : null}
    </Screen>
  );
}

function ExerciseMediaPanel({
  detail,
  effectivePresentation,
  mediaIndex,
  mediaItems,
  onMediaIndexChange,
  onPresentationChange,
  runtimeApiBaseUrl,
  selectedItem,
}: {
  readonly detail: ExerciseDetail;
  readonly effectivePresentation: MediaPresentationChoice;
  readonly mediaIndex: number;
  readonly mediaItems: ExerciseMediaItem[];
  readonly onMediaIndexChange: (index: number) => void;
  readonly onPresentationChange: (presentation: MediaPresentationChoice) => void;
  readonly runtimeApiBaseUrl: string;
  readonly selectedItem: ExerciseMediaItem | undefined;
}) {
  const name = exerciseTitle(detail.name_fa, detail.name_en);
  return (
    <Card style={styles.mediaCard}>
      <View style={styles.mediaHeader}>
        <Text style={styles.mediaTitle}>{name}</Text>
        <Text style={styles.mediaSecondary}>{exerciseSecondaryTitle(detail.name_fa, detail.name_en)}</Text>
      </View>
      <View style={styles.presentationRow}>
        <Text style={styles.filterLabel}>{exerciseCopy.selectedMedia}</Text>
        <PresentationChip
          label={exerciseCopy.videoFemale}
          selected={effectivePresentation === "female"}
          onPress={() => onPresentationChange("female")}
        />
        <PresentationChip
          label={exerciseCopy.videoMale}
          selected={effectivePresentation === "male"}
          onPress={() => onPresentationChange("male")}
        />
      </View>
      {selectedItem !== undefined && selectedItem.mediaType !== "placeholder" ? (
        <NativeExerciseMedia
          item={selectedItem}
          name={name}
          runtimeApiBaseUrl={runtimeApiBaseUrl}
        />
      ) : (
        <View accessibilityRole="image" style={styles.mediaFallback}>
          <Text style={styles.mediaFallbackText}>{exerciseCopy.mediaUnavailable}</Text>
        </View>
      )}
      {mediaItems.length > 1 ? (
        <View style={styles.mediaSelector}>
          <Text style={styles.mediaCount}>
            {exerciseCopy.selectedMediaCount(mediaIndex + 1, mediaItems.length)}
          </Text>
          <View style={styles.mediaChoices}>
            {mediaItems.map((item, index) => (
              <PresentationChip
                key={item.key}
                label={mediaItemLabel(item, index)}
                selected={index === mediaIndex}
                onPress={() => onMediaIndexChange(index)}
              />
            ))}
          </View>
        </View>
      ) : null}
      {selectedItem?.mediaAttribution ? (
        <Text style={styles.attribution}>
          {exerciseCopy.mediaAttribution}: {selectedItem.mediaAttribution}
        </Text>
      ) : null}
    </Card>
  );
}

function NativeExerciseMedia({
  item,
  name,
  runtimeApiBaseUrl,
}: {
  readonly item: ExerciseMediaItem;
  readonly name: string;
  readonly runtimeApiBaseUrl: string;
}) {
  const source = { uri: resolveExerciseMediaUrl(item.mediaPath, runtimeApiBaseUrl) };
  if (item.mediaType === "video") {
    return (
      <Media
        accessibilityLabel={`نمایش حرکت ${name}`}
        contentFit="contain"
        kind="video"
        nativeControls
        source={source}
        style={styles.media}
      />
    );
  }
  return (
    <Media
      accessibilityLabel={`نمایش حرکت ${name}`}
      source={source}
      style={styles.media}
    />
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

function PresentationChip({
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
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={[styles.presentationChip, selected && styles.presentationChipSelected]}
    >
      <Text style={[styles.presentationChipText, selected && styles.presentationChipTextSelected]}>
        {label}
      </Text>
    </Pressable>
  );
}

function DetailSkeleton() {
  return (
    <View style={styles.skeletonGroup}>
      <Skeleton height={260} />
      <Skeleton height={130} />
      <Skeleton height={180} />
    </View>
  );
}

function mediaItemLabel(item: ExerciseMediaItem, index: number): string {
  const presentation = item.presentation === "female"
    ? exerciseCopy.videoFemale
    : item.presentation === "male"
      ? exerciseCopy.videoMale
      : "رسانه";
  return `${presentation} ${index + 1}`;
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
  attribution: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 18,
    textAlign: "right",
    writingDirection: "rtl",
  },
  eyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  filterLabel: {
    color: fiticianTokens.colors.muted,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  header: {
    alignItems: "flex-end",
    gap: fiticianTokens.spacing[2],
    marginBottom: fiticianTokens.spacing[4],
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
  media: {
    height: 260,
    width: "100%",
  },
  mediaCard: {
    gap: fiticianTokens.spacing[3],
  },
  mediaChoices: {
    alignItems: "flex-start",
    flexDirection: "row-reverse",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  mediaCount: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  mediaFallback: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    height: 260,
    justifyContent: "center",
    padding: fiticianTokens.spacing[4],
  },
  mediaFallbackText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    textAlign: "center",
    writingDirection: "rtl",
  },
  mediaHeader: {
    gap: fiticianTokens.spacing[1],
  },
  mediaSecondary: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "ltr",
  },
  mediaSelector: {
    gap: fiticianTokens.spacing[2],
  },
  mediaTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h2,
    lineHeight: 32,
    textAlign: "right",
    writingDirection: "rtl",
  },
  mutedText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    textAlign: "right",
    writingDirection: "rtl",
  },
  presentationChip: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  presentationChipSelected: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderColor: fiticianTokens.colors.aqua,
  },
  presentationChipText: {
    color: fiticianTokens.colors.mist,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "center",
    writingDirection: "rtl",
  },
  presentationChipTextSelected: {
    color: fiticianTokens.colors.canvas,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
  },
  presentationRow: {
    alignItems: "center",
    flexDirection: "row-reverse",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  sectionTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "rtl",
  },
  skeletonGroup: {
    gap: fiticianTokens.spacing[3],
  },
  warningCard: {
    borderColor: fiticianTokens.colors.amber,
  },
});
