import { useRouter } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import { Button, Card, ProgressBar } from "../ui/components";
import { ExerciseMedia } from "../exercises/ExerciseMedia";
import type { WorkoutDay } from "../workouts/workoutApi";

export type WorkoutHomeState = "empty" | "error" | "loading" | "offline" | "ready" | "stale";

export interface WorkoutTodayCardProps {
  readonly day: WorkoutDay | null;
  readonly state: WorkoutHomeState;
}

export function WorkoutTodayCard({ day, state }: WorkoutTodayCardProps) {
  const router = useRouter();
  const firstExercise = day?.exercises[0];
  const title = day?.title_fa || day?.title_en || "تمرین امروز";
  const canStart = day !== null && state === "ready";

  return (
    <Card style={styles.card} variant="hero">
      <View style={styles.heading}>
        <View style={styles.headingCopy}>
          <Text style={styles.eyebrow}>تمرین امروز</Text>
          <Text style={styles.title}>{title}</Text>
        </View>
        <View style={styles.dayBadge}>
          <Text style={styles.dayNumber}>{day ? String(day.day_number).padStart(2, "0") : "—"}</Text>
          <Text style={styles.dayLabel}>روز</Text>
        </View>
      </View>

      {firstExercise ? (
        <View style={styles.mediaWrap}>
          <ExerciseMedia
            accessibilityLabel={`رسانه تمرین ${firstExercise.exercise.name_fa || firstExercise.exercise.name_en}`}
            autoplay
            mediaType={firstExercise.exercise.media_type}
            name={firstExercise.exercise.name_fa || firstExercise.exercise.name_en}
            path={firstExercise.exercise.media_path}
            style={styles.media}
          />
          <View pointerEvents="none" style={styles.mediaScrim} />
          <View pointerEvents="none" style={styles.mediaCaption}>
            <Text style={styles.mediaLabel}>حرکت اول</Text>
            <Text style={styles.mediaTitle}>{firstExercise.exercise.name_fa || firstExercise.exercise.name_en}</Text>
          </View>
        </View>
      ) : (
        <View style={styles.emptyMedia}>
          <Text style={styles.emptyMediaTitle}>برنامه‌ات آماده می‌شود</Text>
          <Text style={styles.emptyMediaText}>با تکمیل پروفایل تمرینی، جلسه امروز را ببین.</Text>
        </View>
      )}

      <View style={styles.metaRow}>
        <MetaItem label="مدت جلسه" value={day ? `${day.estimated_duration_minutes} دقیقه` : "—"} />
        <MetaItem label="حرکت‌ها" value={day ? `${day.total_exercise_count} حرکت` : "—"} />
        <MetaItem label="وضعیت" value={stateLabel(state, Boolean(day))} />
      </View>

      {state === "loading" ? <ProgressBar label="در حال بارگذاری تمرین" progress={0.36} /> : null}
      {state === "offline" && day !== null ? <Text style={styles.stateText}>آخرین برنامه ذخیره‌شده نمایش داده می‌شود.</Text> : null}
      {state === "stale" && day !== null ? <Text style={styles.stateText}>آخرین نسخه ذخیره‌شده نمایش داده می‌شود.</Text> : null}
      {state === "error" ? <Text style={styles.stateText}>دریافت برنامه انجام نشد؛ دوباره از بخش تمرین تلاش کن.</Text> : null}

      <Button
        disabled={state === "loading"}
        label={canStart ? "شروع تمرین" : "مشاهده برنامه تمرینی"}
        onPress={() => router.push("/member/workouts")}
        variant="primary"
      />
    </Card>
  );
}

function MetaItem({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <View style={styles.metaItem}>
      <Text style={styles.metaValue}>{value}</Text>
      <Text style={styles.metaLabel}>{label}</Text>
    </View>
  );
}

function stateLabel(state: WorkoutHomeState, hasDay: boolean): string {
  if (state === "loading") return "در حال خواندن";
  if (state === "offline") return "آفلاین";
  if (state === "stale") return "قدیمی";
  if (state === "error") return "خطا";
  if (!hasDay) return "بدون برنامه";
  return "آماده";
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#0d211e",
    gap: 16,
    overflow: "hidden",
    padding: 16,
  },
  dayBadge: {
    alignItems: "center",
    backgroundColor: "rgba(80,223,206,0.12)",
    borderColor: "rgba(80,223,206,0.28)",
    borderRadius: 16,
    borderWidth: 1,
    minWidth: 58,
    paddingHorizontal: 8,
    paddingVertical: 8,
  },
  dayLabel: {
    color: "#94aba5",
    fontFamily: "Vazirmatn",
    fontSize: 11,
    writingDirection: "rtl",
  },
  dayNumber: {
    color: "#50dfce",
    fontFamily: "Sora",
    fontSize: 24,
    fontWeight: "800",
  },
  emptyMedia: {
    alignItems: "center",
    backgroundColor: "#091817",
    borderRadius: 18,
    gap: 8,
    justifyContent: "center",
    minHeight: 184,
    padding: 24,
  },
  emptyMediaText: {
    color: "#94aba5",
    fontFamily: "Vazirmatn",
    fontSize: 13,
    lineHeight: 22,
    textAlign: "center",
    writingDirection: "rtl",
  },
  emptyMediaTitle: {
    color: "#e8f4f1",
    fontFamily: "Lalezar",
    fontSize: 20,
    textAlign: "center",
    writingDirection: "rtl",
  },
  eyebrow: {
    color: "#50dfce",
    fontFamily: "Vazirmatn",
    fontSize: 13,
    fontWeight: "700",
    textAlign: "right",
    writingDirection: "rtl",
  },
  heading: {
    alignItems: "flex-start",
    flexDirection: "row-reverse",
    gap: 12,
    justifyContent: "space-between",
  },
  headingCopy: {
    flex: 1,
    gap: 4,
  },
  media: {
    borderRadius: 18,
    height: 220,
    minHeight: 220,
  },
  mediaCaption: {
    bottom: 14,
    left: 16,
    position: "absolute",
    right: 16,
  },
  mediaLabel: {
    color: "#50dfce",
    fontFamily: "Vazirmatn",
    fontSize: 12,
    fontWeight: "700",
    textAlign: "right",
    writingDirection: "rtl",
  },
  mediaScrim: {
    backgroundColor: "rgba(2,6,7,0.56)",
    bottom: 0,
    left: 0,
    position: "absolute",
    right: 0,
    top: 108,
  },
  mediaTitle: {
    color: "#e8f4f1",
    fontFamily: "Lalezar",
    fontSize: 22,
    lineHeight: 30,
    textAlign: "right",
    writingDirection: "rtl",
  },
  mediaWrap: {
    borderRadius: 18,
    overflow: "hidden",
  },
  metaItem: {
    flex: 1,
    gap: 3,
  },
  metaLabel: {
    color: "#94aba5",
    fontFamily: "Vazirmatn",
    fontSize: 11,
    textAlign: "right",
    writingDirection: "rtl",
  },
  metaRow: {
    flexDirection: "row-reverse",
    gap: 12,
  },
  metaValue: {
    color: "#e8f4f1",
    fontFamily: "Vazirmatn",
    fontSize: 13,
    fontWeight: "700",
    textAlign: "right",
    writingDirection: "rtl",
  },
  stateText: {
    color: "#f2b85b",
    fontFamily: "Vazirmatn",
    fontSize: 12,
    lineHeight: 20,
    textAlign: "right",
    writingDirection: "rtl",
  },
  title: {
    color: "#e8f4f1",
    fontFamily: "Lalezar",
    fontSize: 25,
    lineHeight: 34,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
