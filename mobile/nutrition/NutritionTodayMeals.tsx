import { useRouter } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import { Button, Card } from "../ui/components";
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
        <Button label="ثبت وعده" onPress={() => router.push("/member/nutrition-tracking")} variant="ghost" />
      </View>
      <View style={styles.rows}>
        {day.meals.map((meal) => <MealRow key={meal.id} meal={meal} />)}
      </View>
    </Card>
  );
}

function MealRow({ meal }: { readonly meal: WeeklyPlanMeal }) {
  const calories = meal.nutrient_totals.energy_kcal;
  return (
    <View style={styles.row}>
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
    textAlign: "left",
  },
  card: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    gap: 0,
    marginBottom: fiticianTokens.spacing[1],
    overflow: "hidden",
    padding: 0,
  },
  header: {
    alignItems: "center",
    borderBottomColor: fiticianTokens.colors.line,
    borderBottomWidth: 1,
    flexDirection: "row-reverse",
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
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
    minHeight: 46,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  rows: {
    gap: 0,
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
