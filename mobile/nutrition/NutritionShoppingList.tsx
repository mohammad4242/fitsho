import { useQuery } from "@tanstack/react-query";
import { StyleSheet, Text, View } from "react-native";

import { nutritionKeys } from "../data/queryKeys";
import type { ConnectivityStatus } from "../platform/connectivity";
import { DisclosureCard, Notice, Skeleton } from "../ui/components";
import { getMobileViewState } from "../ui/requestState";
import { fiticianTokens } from "../ui/tokens";
import { formatNutritionPlanMoney } from "./nutritionPlanModel";
import { type NutritionPlanApi } from "./nutritionPlanApi";
import {
  approvedShoppingPriceVisibility,
  formatShoppingQuantity,
  type ShoppingList,
  type ShoppingPriceVisibility,
} from "./nutritionShoppingList";

const shoppingWarningMessages: Readonly<Record<string, string>> = {
  INSUFFICIENT_PRICE_COVERAGE: "پوشش قیمت مرجع برای همه مواد غذایی کافی نیست.",
  PHYSICIAN_REVIEW_REQUIRED: "این نسخه تا بررسی پزشک برای خرید نهایی آماده نیست.",
  PRICE_SNAPSHOT_STALE: "قیمت‌های مرجع این نسخه ممکن است تازه نباشند.",
};

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
  return (
    <DisclosureCard
      defaultExpanded={false}
      style={styles.card}
      summary="مواد لازم برای این نسخه از برنامه"
      title="لیست خرید"
    >
      {state.status === "loading" ? <Skeleton height={260} /> : null}
      {state.status === "error" && list === undefined ? (
        <Notice
          actionLabel="تلاش دوباره"
          message="لیست خرید برنامه دریافت نشد."
          onAction={() => void query.refetch()}
          variant="danger"
        />
      ) : null}
      {state.status === "offline" && list === undefined ? (
        <Notice message="لیست خرید در حالت آفلاین در دسترس نیست." variant="offline" />
      ) : null}
      {list !== undefined ? (
        <ShoppingListContent
          list={list}
          priceVisibility={approvedShoppingPriceVisibility(list, executable)}
        />
      ) : null}
    </DisclosureCard>
  );
}

function ShoppingListContent({
  list,
  priceVisibility,
}: {
  readonly list: ShoppingList;
  readonly priceVisibility: ShoppingPriceVisibility;
}) {
  return (
    <>
      {priceVisibility === "not_executable" ? (
        <Notice message="قیمت مرجع فقط برای برنامه فعال و تأییدشده نمایش داده می‌شود." variant="warning" />
      ) : null}
      <ShoppingWarnings codes={list.warning_codes} />
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
          <Text style={styles.totalLabel}>جمع هزینه مرجع تأییدشده</Text>
          <Text style={styles.totalValue}>{formatNutritionPlanMoney(list.total_cost_irr)}</Text>
        </View>
      ) : null}
    </>
  );
}

function stateData<TData>(state: ReturnType<typeof getMobileViewState<TData>>): TData | undefined {
  if (state.status === "loading") return undefined;
  return "data" in state ? state.data : undefined;
}

function ShoppingWarnings({ codes }: { readonly codes: readonly string[] }) {
  const messages = [...new Set(codes.map((code) => shoppingWarningMessages[code]).filter((message): message is string => message !== undefined))];
  if (messages.length === 0) return null;
  return <Notice message={messages.join(" ")} title="وضعیت برنامه" variant="info" />;
}

const styles = StyleSheet.create({
  card: {
    marginTop: fiticianTokens.spacing[3],
  },
  english: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "left",
    writingDirection: "ltr",
  },
  item: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    padding: fiticianTokens.spacing[3],
  },
  itemAmount: {
    alignItems: "stretch",
    flexShrink: 0,
    gap: fiticianTokens.spacing[1],
  },
  itemCopy: {
    alignItems: "stretch",
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  itemEnglish: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "left",
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
    textAlign: "right",
    writingDirection: "rtl",
  },
  quantity: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
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
    flexDirection: "row",
    justifyContent: "space-between",
    paddingTop: fiticianTokens.spacing[3],
  },
  totalValue: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
});
