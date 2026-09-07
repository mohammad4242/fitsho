import { useQuery } from "@tanstack/react-query";
import { StyleSheet, Text, View } from "react-native";

import { nutritionKeys } from "../data/queryKeys";
import type { ConnectivityStatus } from "../platform/connectivity";
import { Card, Notice, Skeleton } from "../ui/components";
import { getMobileViewState } from "../ui/requestState";
import { fiticianTokens } from "../ui/tokens";
import { formatNutritionPlanMoney } from "./nutritionPlanModel";
import { type NutritionPlanApi } from "./nutritionPlanApi";
import {
  approvedShoppingPriceVisibility,
  formatShoppingQuantity,
} from "./nutritionShoppingList";

export function NutritionShoppingList({
  api,
  connectivityStatus,
  executable,
  historical,
  planId,
}: {
  readonly api: NutritionPlanApi;
  readonly connectivityStatus: ConnectivityStatus;
  readonly executable: boolean;
  readonly historical: boolean;
  readonly planId: string;
}) {
  const query = useQuery({
    enabled: !historical,
    queryFn: () => api.getShoppingList(planId),
    queryKey: nutritionKeys.shoppingList(planId),
  });
  const state = getMobileViewState(query, { connectivityStatus });
  const list = stateData(state);

  if (historical) return null;
  if (state.status === "loading") return <Skeleton height={260} />;
  if (state.status === "error" && list === undefined) {
    return (
      <Notice
        actionLabel="تلاش دوباره"
        message="لیست خرید برنامه دریافت نشد."
        onAction={() => void query.refetch()}
        variant="danger"
      />
    );
  }
  if (state.status === "offline" && list === undefined) {
    return <Notice message="لیست خرید در حالت آفلاین در دسترس نیست." variant="offline" />;
  }
  if (list === undefined) return null;

  const priceVisibility = approvedShoppingPriceVisibility(list, executable);
  return (
    <Card style={styles.card}>
      <View style={styles.heading}>
        <Text style={styles.title}>لیست خرید</Text>
        <Text style={styles.subtitle}>مواد لازم برای این نسخه از برنامه</Text>
      </View>
      {state.status === "offline" || state.status === "stale" ? (
        <Notice message="این لیست تازه‌سازی نشده است؛ قبل از خرید اتصال را بررسی کن." variant="offline" />
      ) : null}
      {priceVisibility === "not_approved" ? (
        <Notice message="قیمت نهایی تا تأیید پزشک نمایش داده نمی‌شود." variant="warning" />
      ) : null}
      {priceVisibility === "not_executable" ? (
        <Notice message="قیمت مرجع فقط برای برنامه فعال و تأییدشده نمایش داده می‌شود." variant="warning" />
      ) : null}
      {list.warning_codes.length > 0 ? (
        <Notice message={list.warning_codes.join("\n")} title="وضعیت برنامه" variant="info" />
      ) : null}
      {list.items.length === 0 ? (
        <Notice message="برای این نسخه ماده‌ای در لیست خرید ثبت نشده است." variant="info" />
      ) : (
        <View style={styles.itemStack}>
          {list.items.map((item) => (
            <View key={item.food_id} style={styles.item}>
              <View style={styles.itemCopy}>
                <Text style={styles.itemName}>{item.name_fa}</Text>
                <Text style={styles.itemEnglish}>{item.name_en}</Text>
              </View>
              <View style={styles.itemAmount}>
                <Text style={styles.quantity}>
                  {formatShoppingQuantity(item.required_quantity)} {item.canonical_unit}
                </Text>
                {priceVisibility === "approved" ? (
                  <Text style={styles.price}>{formatNutritionPlanMoney(item.cost_irr)}</Text>
                ) : null}
              </View>
            </View>
          ))}
        </View>
      )}
      {priceVisibility === "approved" ? (
        <View style={styles.totalRow}>
          <Text style={styles.totalValue}>{formatNutritionPlanMoney(list.total_cost_irr)}</Text>
          <Text style={styles.totalLabel}>جمع هزینه مرجع تأییدشده</Text>
        </View>
      ) : null}
    </Card>
  );
}

function stateData<TData>(state: ReturnType<typeof getMobileViewState<TData>>): TData | undefined {
  if (state.status === "loading") return undefined;
  return "data" in state ? state.data : undefined;
}

const styles = StyleSheet.create({
  card: {
    gap: fiticianTokens.spacing[3],
    marginTop: fiticianTokens.spacing[3],
  },
  english: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "left",
    writingDirection: "ltr",
  },
  heading: {
    alignItems: "flex-end",
    gap: fiticianTokens.spacing[1],
  },
  item: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    padding: fiticianTokens.spacing[3],
  },
  itemAmount: {
    alignItems: "flex-start",
    flexShrink: 0,
    gap: fiticianTokens.spacing[1],
  },
  itemCopy: {
    alignItems: "flex-end",
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  itemEnglish: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "ltr",
  },
  itemName: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  itemStack: {
    gap: fiticianTokens.spacing[2],
  },
  price: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "left",
    writingDirection: "rtl",
  },
  quantity: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "left",
    writingDirection: "rtl",
  },
  subtitle: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
    textAlign: "right",
    writingDirection: "rtl",
  },
  title: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "rtl",
  },
  totalLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  totalRow: {
    alignItems: "center",
    borderTopColor: fiticianTokens.colors.lineStrong,
    borderTopWidth: 1,
    flexDirection: "row-reverse",
    justifyContent: "space-between",
    paddingTop: fiticianTokens.spacing[3],
  },
  totalValue: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "left",
    writingDirection: "rtl",
  },
});
