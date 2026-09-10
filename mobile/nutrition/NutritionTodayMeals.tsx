import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { Card } from "../ui/components";
import { fiticianTokens } from "../ui/tokens";
import type { WeeklyPlan, WeeklyPlanMeal } from "./nutritionPlanApi";

export function NutritionTodayMeals({ plan }: { readonly plan: WeeklyPlan | null }) {
  const router = useRouter();
  const day = plan?.days.find((item) => item.plan_date === todayIsoDate()) ?? plan?.days[0];
  if (day === undefined) return null;

  return (
    <Card accessibilityLabel="وعده‌های امروز" style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.title}>وعده‌های امروز</Text>
        <Pressable
          accessibilityLabel="ثبت وعده"
          accessibilityRole="button"
          onPress={() => router.push("/member/nutrition-tracking")}
          style={({ pressed }) => [styles.trackAction, pressed && styles.pressed]}
        >
          <Text style={styles.trackActionText}>ثبت وعده</Text>
        </Pressable>
      </View>
      <View style={styles.rows}>
        {day.meals.map((meal, index) => <MealRow key={meal.id} meal={meal} showDivider={index > 0} />)}
      </View>
    </Card>
  );
}

function MealRow({ meal, showDivider }: { readonly meal: WeeklyPlanMeal; readonly showDivider: boolean }) {
  const calories = meal.nutrient_totals.energy_kcal;
  return (
    <View style={[styles.row, showDivider && styles.dividedRow]}>
      <Text style={styles.mealName}>{mealLabel(meal.slot_role, meal.slot_index)}</Text>
      <Text style={styles.calories}>
        {calories === undefined ? "—" : `${formatNumber(calories)} کیلوکالری`}
      </Text>
    </View>
  );
}

function mealLabel(role: string, index: number): string {
  if (role === "free_meal") return "وعده آزاد";
  if (role === "post_workout") return "پس از تمرین";
  if (role === "snack") return `میان‌وعده ${formatNumber(index + 1)}`;
  return ["صبحانه", "ناهار", "شام"][index] ?? `وعده ${formatNumber(index + 1)}`;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1 }).format(value);
}

function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

const styles = StyleSheet.create({
  calories: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  card: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    gap: 0,
    marginBottom: fiticianTokens.spacing[1],
    overflow: "hidden",
    padding: 0,
  },
  dividedRow: {
    borderTopColor: fiticianTokens.colors.line,
    borderTopWidth: 1,
  },
  header: {
    alignItems: "center",
    borderBottomColor: fiticianTokens.colors.line,
    borderBottomWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    minHeight: 58,
    paddingHorizontal: fiticianTokens.spacing[3],
  },
  mealName: {
    color: fiticianTokens.colors.muted,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  row: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
    minHeight: 46,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  pressed: {
    opacity: 0.76,
  },
  rows: {
    gap: 0,
  },
  trackAction: {
    alignItems: "center",
    justifyContent: "center",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    minWidth: fiticianTokens.layout.minimumTouchTarget,
  },
  trackActionText: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
