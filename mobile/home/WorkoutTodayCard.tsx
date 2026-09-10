import { useRouter } from "expo-router";
import { StyleSheet, Text, View, useWindowDimensions } from "react-native";

import { ExerciseMedia } from "../exercises/ExerciseMedia";
import type { WorkoutDay } from "../workouts/workoutApi";
import { Button, CinematicSurface, StateSkeleton } from "../ui/components";
import { formatPersianNumber } from "../ui/locale";
import { fiticianTokens } from "../ui/tokens";
import { getHomeHeroLayout } from "./homePresentation";

export type WorkoutHomeState = "empty" | "error" | "loading" | "offline" | "ready" | "stale";

export interface WorkoutTodayCardProps {
  readonly day: WorkoutDay | null;
  readonly state: WorkoutHomeState;
}

export function WorkoutTodayCard({ day, state }: WorkoutTodayCardProps) {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const stacked = getHomeHeroLayout(width) === "stacked";
  const firstExercise = day?.exercises[0];
  const title = day?.title_fa || day?.title_en || "تمرین امروز";
  const canStart = day !== null && state === "ready";

  if (state === "loading" && day === null) return <StateSkeleton variant="hero" />;

  return (
    <CinematicSurface accent style={styles.card} variant="hero">
      <View style={[styles.layout, stacked && styles.layoutStacked]}>
        <View style={[styles.mediaWrap, stacked && styles.mediaStacked]}>
          {firstExercise ? (
            <ExerciseMedia
              accessibilityLabel={`رسانه تمرین ${firstExercise.exercise.name_fa || firstExercise.exercise.name_en}`}
              autoplay
              mediaType={firstExercise.exercise.media_type}
              name={firstExercise.exercise.name_fa || firstExercise.exercise.name_en}
              path={firstExercise.exercise.media_path}
              style={styles.media}
            />
          ) : (
            <View style={styles.emptyMedia}>
              <Text style={styles.emptyMediaText}>جلسه بعدی پس از آماده‌شدن برنامه اینجا دیده می‌شود.</Text>
            </View>
          )}
          <View pointerEvents="none" style={styles.mediaScrim} />
        </View>

        <View style={styles.copy}>
          <View style={styles.topLine}>
            <View style={styles.statusPill}>
              <View style={styles.statusDot} />
              <Text style={styles.statusText}>{stateLabel(state, Boolean(day))}</Text>
            </View>
            <Text style={styles.eyebrow}>تمرین امروز</Text>
          </View>
          <Text numberOfLines={3} style={styles.title}>{title}</Text>
          <View style={styles.dayLine}>
            <View style={styles.dayBadge}>
              <Text style={styles.dayNumber}>{day ? formatPersianNumber(day.day_number, { maximumFractionDigits: 0, useGrouping: false }).padStart(2, "۰") : "—"}</Text>
            </View>
            <View style={styles.sessionFacts}>
              <Text style={styles.factValue}>{day ? `${formatPersianNumber(day.estimated_duration_minutes, { maximumFractionDigits: 0 })} دقیقه` : "—"}</Text>
            </View>
          </View>
          {state === "error" ? (
            <Text style={styles.stateText}>دریافت برنامه انجام نشد؛ از بخش تمرین دوباره تلاش کن.</Text>
          ) : null}
          <Button
            label={canStart ? "شروع تمرین" : "مشاهده برنامه"}
            onPress={() => router.push("/member/workouts")}
            style={styles.action}
          />
        </View>
      </View>
    </CinematicSurface>
  );
}

function stateLabel(state: WorkoutHomeState, hasDay: boolean): string {
  if (state === "offline") return "آفلاین";
  if (state === "stale") return "ذخیره‌شده";
  if (state === "error") return "خطا";
  if (!hasDay) return "بدون برنامه";
  return "برنامه فعال";
}

const styles = StyleSheet.create({
  action: {
    alignSelf: "stretch",
    marginTop: "auto",
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  card: { minHeight: 204, width: "100%" },
  copy: { flex: 1.05, gap: fiticianTokens.spacing[2], padding: fiticianTokens.spacing[3] },
  dayBadge: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    height: 44,
    justifyContent: "center",
    width: 44,
  },
  dayLine: { alignItems: "center", flexDirection: "row", gap: fiticianTokens.spacing[2] },
  dayNumber: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.h3,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    writingDirection: "ltr",
  },
  emptyMedia: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.petrol,
    flex: 1,
    gap: fiticianTokens.spacing[2],
    justifyContent: "center",
    padding: fiticianTokens.spacing[4],
  },
  emptyMediaText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 19,
    textAlign: "center",
    writingDirection: "rtl",
  },
  eyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  factValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  layout: { flexDirection: "row", minHeight: 204 },
  layoutStacked: { flexDirection: "column" },
  media: { borderRadius: 0, flex: 1, minHeight: 204 },
  mediaScrim: {
    backgroundColor: fiticianTokens.colors.scrim,
    bottom: 0,
    left: 0,
    position: "absolute",
    right: 0,
    top: "54%",
  },
  mediaStacked: { flex: 0, height: 120, minHeight: 120 },
  mediaWrap: {
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    flex: 1.15,
    minHeight: 204,
    overflow: "hidden",
    position: "relative",
  },
  sessionFacts: { flex: 1 },
  stateText: {
    color: fiticianTokens.colors.amber,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    lineHeight: 17,
    textAlign: "right",
    writingDirection: "rtl",
  },
  statusDot: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.pill,
    height: 5,
    width: 5,
  },
  statusPill: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderRadius: fiticianTokens.radii.pill,
    flexDirection: "row",
    gap: 5,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: 5,
  },
  statusText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 9,
    textAlign: "center",
    writingDirection: "rtl",
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h2,
    lineHeight: 31,
    textAlign: "right",
    writingDirection: "rtl",
  },
  topLine: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    justifyContent: "space-between",
  },
});
