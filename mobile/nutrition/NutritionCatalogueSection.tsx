import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { nutritionKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import {
  Button,
  Card,
  EmptyState,
  Notice,
  PageHeading,
  SegmentedControl,
  Sheet,
  Skeleton,
  TextField,
} from "../ui/components";
import { getMobileViewState } from "../ui/requestState";
import { formatPersianNumber } from "../ui/locale";
import { fiticianTokens } from "../ui/tokens";
import {
  createNutritionCatalogueApi,
  type FoodCatalogueItem,
  type MealCatalogueCategory,
  type MealCatalogueItem,
} from "./nutritionCatalogueApi";
import {
  foodCatalogueMacroRows,
  foodCatalogueCategoryLabel,
  foodCataloguePortionRows,
  mealCatalogueCategoryLabel,
  preparedMealCatalogueLabel,
  selectDefaultFoodPortion,
} from "./nutritionCatalogueModel";
import { NutritionThumbnail } from "./NutritionThumbnail";

type CatalogueMode = "foods" | "meals";

export function NutritionCatalogueSection({ initialMode }: { readonly initialMode?: CatalogueMode } = {}) {
  const auth = useMobileAuth();
  const connectivityStatus = useConnectivityStatus();
  const api = useMemo(() => createNutritionCatalogueApi(auth.request), [auth.request]);
  const dedicatedMode = initialMode !== undefined;
  const [mode, setMode] = useState<CatalogueMode>(initialMode ?? "foods");
  const [query, setQuery] = useState("");
  const [foodCategory, setFoodCategory] = useState<string | null>(null);
  const [mealCategory, setMealCategory] = useState<MealCatalogueCategory | null>(null);
  const [selectedFood, setSelectedFood] = useState<FoodCatalogueItem | null>(null);
  const [selectedMeal, setSelectedMeal] = useState<MealCatalogueItem | null>(null);
  const normalizedQuery = query.trim();
  const foodQuery = useQuery({
    enabled: mode === "foods",
    queryFn: () => api.getFoodCatalogue({
      category: foodCategory ?? undefined,
      page: 1,
      pageSize: 24,
      query: normalizedQuery || undefined,
    }),
    queryKey: nutritionKeys.foodCatalogue({
      category: foodCategory ?? "",
      page: 1,
      pageSize: 24,
      query: normalizedQuery,
    }),
  });
  const mealQuery = useQuery({
    enabled: mode === "meals",
    queryFn: () => api.getMealCatalogue(mealCategory ?? undefined),
    queryKey: nutritionKeys.mealCatalogue(mealCategory),
  });
  const foodState = getMobileViewState(foodQuery, {
    connectivityStatus,
    isEmpty: (data) => data.items.length === 0,
  });
  const mealState = getMobileViewState(mealQuery, {
    connectivityStatus,
    isEmpty: (data) => data.items.length === 0,
  });
  const foodPage = stateData(foodState);
  const mealPage = stateData(mealState);

  return (
    <View style={styles.section}>
      <PageHeading
        eyebrow={dedicatedMode ? "تغذیه · کاتالوگ" : "تغذیه"}
        supportingText={mode === "foods"
          ? "مواد غذایی تأییدشده را جست‌وجو کن و جزئیات هر مورد را ببین."
          : "وعده‌های منتشرشده و مواد تشکیل‌دهنده قابل نمایش را مرور کن."}
        title={mode === "foods" ? "کاتالوگ مواد غذایی" : "کاتالوگ وعده‌ها"}
      />
      {!dedicatedMode ? (
        <SegmentedControl
          accessibilityLabel="نوع کاتالوگ"
          onChange={(value) => {
            if (value === "foods" || value === "meals") setMode(value);
          }}
          options={[{ label: "مواد غذایی", value: "foods" }, { label: "وعده‌ها", value: "meals" }]}
          selectedValue={mode}
        />
      ) : null}
      {mode === "foods" ? (
        <FoodCatalogueView
          category={foodCategory}
          onCategoryChange={setFoodCategory}
          onRetry={() => void foodQuery.refetch()}
          onSelect={setSelectedFood}
          onSearch={setQuery}
          page={foodPage}
          query={query}
          state={foodState}
        />
      ) : (
        <MealCatalogueView
          category={mealCategory}
          onCategoryChange={setMealCategory}
          onRetry={() => void mealQuery.refetch()}
          onSelect={setSelectedMeal}
          page={mealPage}
          state={mealState}
        />
      )}
      <FoodDetailsSheet food={selectedFood} onClose={() => setSelectedFood(null)} />
      <MealDetailsSheet meal={selectedMeal} onClose={() => setSelectedMeal(null)} />
    </View>
  );
}

function FoodCatalogueView({
  category,
  onCategoryChange,
  onRetry,
  onSearch,
  onSelect,
  page,
  query,
  state,
}: {
  readonly category: string | null;
  readonly onCategoryChange: (category: string | null) => void;
  readonly onRetry: () => void;
  readonly onSearch: (query: string) => void;
  readonly onSelect: (food: FoodCatalogueItem) => void;
  readonly page: ReturnType<typeof stateData<FoodCatalogueItemPage>>;
  readonly query: string;
  readonly state: ReturnType<typeof getMobileViewState<FoodCatalogueItemPage>>;
}) {
  if (state.status === "loading") return <Skeleton height={420} />;
  if (state.status === "error" && page === undefined) {
    return <Notice actionLabel="تلاش دوباره" message="کاتالوگ مواد غذایی دریافت نشد." onAction={onRetry} variant="danger" />;
  }
  if (state.status === "offline" && page === undefined) {
    return <Notice message="برای مرور کاتالوگ مواد غذایی به اینترنت وصل شو." variant="offline" />;
  }
  if (page === undefined) return null;

  return (
    <View style={styles.catalogueStack}>
      <TextField
        accessibilityLabel="جستجوی مواد غذایی"
        onChangeText={onSearch}
        placeholder="جستجوی نام فارسی یا انگلیسی"
        textDirection="rtl"
        value={query}
      />
      {state.status === "offline" || state.status === "stale" ? (
        <Notice message="نتایج کاتالوگ تازه‌سازی نشده‌اند." variant="offline" />
      ) : null}
      <CategoryChips
        categories={page.categories}
        onSelect={onCategoryChange}
        selected={category}
      />
      {page.items.length === 0 ? (
        <EmptyState title="ماده غذایی پیدا نشد">عبارت جستجو یا دسته‌بندی را تغییر بده.</EmptyState>
      ) : (
        <View style={styles.cardStack}>
          {page.items.map((food) => (
            <FoodCatalogueCard food={food} key={food.id} onPress={() => onSelect(food)} />
          ))}
        </View>
      )}
      <Text style={styles.pageMeta}>{formatPageMeta(page.page, page.page_size, page.total)}</Text>
      <Text style={styles.disclaimer}>
        این صفحه قیمت زنده یا پیشنهاد تأییدنشده نشان نمی‌دهد؛ قیمت فقط از نسخه تأییدشده برنامه غذایی می‌آید.
      </Text>
    </View>
  );
}

function MealCatalogueView({
  category,
  onCategoryChange,
  onRetry,
  onSelect,
  page,
  state,
}: {
  readonly category: MealCatalogueCategory | null;
  readonly onCategoryChange: (category: MealCatalogueCategory | null) => void;
  readonly onRetry: () => void;
  readonly onSelect: (meal: MealCatalogueItem) => void;
  readonly page: ReturnType<typeof stateData<MealCataloguePage>>;
  readonly state: ReturnType<typeof getMobileViewState<MealCataloguePage>>;
}) {
  if (state.status === "loading") return <Skeleton height={420} />;
  if (state.status === "error" && page === undefined) {
    return <Notice actionLabel="تلاش دوباره" message="کاتالوگ وعده‌ها دریافت نشد." onAction={onRetry} variant="danger" />;
  }
  if (state.status === "offline" && page === undefined) {
    return <Notice message="برای مرور کاتالوگ وعده‌ها به اینترنت وصل شو." variant="offline" />;
  }
  if (page === undefined) return null;

  return (
    <View style={styles.catalogueStack}>
      {state.status === "offline" || state.status === "stale" ? (
        <Notice message="نتایج کاتالوگ تازه‌سازی نشده‌اند." variant="offline" />
      ) : null}
      <CategoryChips
        categories={page.categories}
        labelForCategory={(value) => mealCatalogueCategoryLabel(value as MealCatalogueCategory)}
        onSelect={(value) => onCategoryChange(value as MealCatalogueCategory | null)}
        selected={category}
      />
      {page.items.length === 0 ? (
        <EmptyState title="وعده‌ای پیدا نشد">دسته‌بندی دیگری را انتخاب کن.</EmptyState>
      ) : (
        <View style={styles.cardStack}>
          {page.items.map((meal) => (
            <MealCatalogueCard key={meal.id} meal={meal} onPress={() => onSelect(meal)} />
          ))}
        </View>
      )}
      <Text style={styles.disclaimer}>
        فقط وعده‌های منتشرشده برای اعضا نمایش داده می‌شوند. جزئیات داخلی دستور آماده در اپ منتشر نمی‌شود.
      </Text>
    </View>
  );
}

function FoodCatalogueCard({ food, onPress }: { readonly food: FoodCatalogueItem; readonly onPress: () => void }) {
  const defaultPortion = selectDefaultFoodPortion(food);
  return (
    <Card onPress={onPress} style={styles.catalogueCard} variant="interactive">
      <View style={styles.catalogueIdentity}>
        <NutritionThumbnail imageUrl={food.image_url} name={food.name_fa} shape="circle" style={styles.catalogueThumbnail} />
        <View style={styles.cardHeading}>
          <View style={styles.cardCopy}>
            <Text style={styles.cardTitle}>{food.name_fa}</Text>
            <Text style={styles.cardEnglish}>{food.name_en}</Text>
          </View>
          <Text style={styles.category}>{foodCatalogueCategoryLabel(food.category)}</Text>
        </View>
      </View>
      <View style={styles.macroRow}>
        {foodCatalogueMacroRows(food).slice(0, 4).map((macro) => (
          <View key={macro.code} style={styles.macroItem}>
            <Text style={styles.macroValue}>{macro.value}</Text>
            <Text style={styles.macroLabel}>{macro.label}</Text>
          </View>
        ))}
      </View>
      <Text style={styles.portionHint}>
        پیمانه پیش‌فرض: {defaultPortion?.label_fa ?? "—"} · {defaultPortion?.grams ?? "—"} گرم
      </Text>
    </Card>
  );
}

function MealCatalogueCard({ meal, onPress }: { readonly meal: MealCatalogueItem; readonly onPress: () => void }) {
  const prepared = preparedMealCatalogueLabel(meal.calculation_mode);
  return (
    <Card onPress={onPress} style={styles.catalogueCard} variant="interactive">
      <View style={styles.catalogueIdentity}>
        <NutritionThumbnail imageUrl={meal.image_url} name={meal.name_fa} style={styles.catalogueThumbnail} />
        <View style={styles.cardHeading}>
          <View style={styles.cardCopy}>
            <Text style={styles.cardTitle}>{meal.name_fa}</Text>
            <Text style={styles.cardEnglish}>{meal.name_en}</Text>
          </View>
          <Text style={styles.category}>{mealCatalogueCategoryLabel(meal.category)}</Text>
        </View>
      </View>
      <Text style={styles.portionHint}>{formatPersianNumber(meal.items.length, { maximumFractionDigits: 0 })} ماده تأییدشده در این وعده</Text>
      {prepared ? <Notice message={prepared.message} title={prepared.title} variant="info" /> : null}
    </Card>
  );
}

function FoodDetailsSheet({ food, onClose }: { readonly food: FoodCatalogueItem | null; readonly onClose: () => void }) {
  return (
    <Sheet onClose={onClose} title={food?.name_fa ?? "جزئیات ماده غذایی"} visible={food !== null}>
      {food ? (
        <View style={styles.sheetStack}>
          <NutritionThumbnail imageUrl={food.image_url} name={food.name_fa} style={styles.sheetThumbnail} />
          <Text style={styles.cardEnglish}>{food.name_en}</Text>
          <Text style={styles.disclaimer}>
            مقادیر زیر برای نمایش گرد شده‌اند؛ محاسبات برنامه با دقت ذخیره‌شده سمت سرور انجام می‌شوند.
          </Text>
          <Text style={styles.sheetTitle}>ماکروها در ۱۰۰ گرم</Text>
          <View style={styles.detailStack}>
            {foodCatalogueMacroRows(food).map((macro) => (
              <SummaryRow key={macro.code} label={macro.label} value={macro.value} />
            ))}
          </View>
          <Text style={styles.sheetTitle}>پیمانه‌ها</Text>
          <View style={styles.detailStack}>
            {foodCataloguePortionRows(food).map((portion) => (
              <SummaryRow
                key={portion.code}
                label={portion.label}
                value={`${portion.quantity} · ${portion.grams} گرم`}
              />
            ))}
          </View>
          <Text style={styles.sourceText}>منبع: {food.source.name} · دادهٔ مرجع ثبت‌شده</Text>
          <Notice message="قیمت این ماده در کاتالوگ عضو نمایش داده نمی‌شود؛ هزینه فقط از برنامه تأییدشده می‌آید." variant="info" />
          <Button label="بستن" onPress={onClose} variant="ghost" />
        </View>
      ) : null}
    </Sheet>
  );
}

function MealDetailsSheet({ meal, onClose }: { readonly meal: MealCatalogueItem | null; readonly onClose: () => void }) {
  return (
    <Sheet onClose={onClose} title={meal?.name_fa ?? "جزئیات وعده"} visible={meal !== null}>
      {meal ? (
        <View style={styles.sheetStack}>
          <NutritionThumbnail imageUrl={meal.image_url} name={meal.name_fa} style={styles.sheetThumbnail} />
          <Text style={styles.cardEnglish}>{meal.name_en}</Text>
          <Text style={styles.sheetTitle}>مواد تشکیل‌دهنده</Text>
          <View style={styles.detailStack}>
            {meal.items.map((item) => (
              <View key={item.food_id} style={styles.ingredientRow}>
                <View style={styles.cardCopy}>
                  <Text style={styles.cardTitle}>{item.food_name_fa}</Text>
                  <Text style={styles.cardEnglish}>{item.food_name_en}</Text>
                </View>
                <Text style={styles.portionHint}>{item.reference_grams} گرم</Text>
              </View>
            ))}
          </View>
          {preparedMealCatalogueLabel(meal.calculation_mode) ? (
            <Notice message="خلاصه قابل نمایش دستور آماده فقط در نسخه غذایی ارائه می‌شود." variant="warning" />
          ) : null}
          <Button label="بستن" onPress={onClose} variant="ghost" />
        </View>
      ) : null}
    </Sheet>
  );
}

function CategoryChips<TCategory extends string>({
  categories,
  labelForCategory,
  onSelect,
  selected,
}: {
  readonly categories: readonly TCategory[];
  readonly labelForCategory?: (category: TCategory) => string;
  readonly onSelect: (category: TCategory | null) => void;
  readonly selected: TCategory | null;
}) {
  return (
    <View style={styles.chipRow}>
      <Chip label="همه" onPress={() => onSelect(null)} selected={selected === null} />
      {categories.map((category) => (
        <Chip
          key={category}
          label={labelForCategory?.(category) ?? category}
          onPress={() => onSelect(category)}
          selected={selected === category}
        />
      ))}
    </View>
  );
}

function Chip({ label, onPress, selected }: { readonly label: string; readonly onPress: () => void; readonly selected: boolean }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={[styles.chip, selected && styles.chipSelected]}
    >
      <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{label}</Text>
    </Pressable>
  );
}

function SummaryRow({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <View style={styles.summaryRow}>
      <Text style={styles.summaryValue}>{value}</Text>
      <Text style={styles.summaryLabel}>{label}</Text>
    </View>
  );
}

function formatPageMeta(page: number, pageSize: number, total: number): string {
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  return `نمایش ${new Intl.NumberFormat("fa-IR").format(from)} تا ${new Intl.NumberFormat("fa-IR").format(to)} از ${new Intl.NumberFormat("fa-IR").format(total)}`;
}

type FoodCatalogueItemPage = Awaited<ReturnType<import("./nutritionCatalogueApi").NutritionCatalogueApi["getFoodCatalogue"]>>;
type MealCataloguePage = Awaited<ReturnType<import("./nutritionCatalogueApi").NutritionCatalogueApi["getMealCatalogue"]>>;

function stateData<TData>(state: ReturnType<typeof getMobileViewState<TData>>): TData | undefined {
  if (state.status === "loading") return undefined;
  return "data" in state ? state.data : undefined;
}

function useConnectivityStatus(): ConnectivityStatus {
  const [status, setStatus] = useState<ConnectivityStatus>(connectivityMonitor.getSnapshot().status);
  useEffect(() => connectivityMonitor.subscribe((snapshot) => setStatus(snapshot.status)), []);
  return status;
}

const styles = StyleSheet.create({
  cardCopy: {
    alignItems: "flex-end",
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  cardEnglish: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "ltr",
  },
  cardHeading: {
    alignItems: "flex-start",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  cardStack: {
    gap: fiticianTokens.spacing[3],
  },
  catalogueIdentity: {
    alignItems: "center",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
  },
  catalogueThumbnail: {
    flexShrink: 0,
  },
  cardTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  category: {
    color: fiticianTokens.colors.aqua,
    flexShrink: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "left",
    writingDirection: "rtl",
  },
  chip: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  chipRow: {
    alignItems: "flex-start",
    flexDirection: "row-reverse",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  chipSelected: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderColor: fiticianTokens.colors.aqua,
  },
  chipText: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  chipTextSelected: {
    color: fiticianTokens.colors.canvas,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
  },
  catalogueCard: {
    gap: fiticianTokens.spacing[3],
  },
  catalogueStack: {
    gap: fiticianTokens.spacing[3],
  },
  disclaimer: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "right",
    writingDirection: "rtl",
  },
  detailStack: {
    gap: fiticianTokens.spacing[2],
  },
  ingredientRow: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
    padding: fiticianTokens.spacing[3],
  },
  macroItem: {
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: "22%",
  },
  macroLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  macroRow: {
    flexDirection: "row-reverse",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  macroValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  pageMeta: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  portionHint: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  section: {
    gap: fiticianTokens.spacing[3],
    marginTop: fiticianTokens.spacing[5],
  },
  sheetStack: {
    gap: fiticianTokens.spacing[3],
  },
  sheetThumbnail: {
    alignSelf: "flex-end",
    height: 128,
    width: 128,
  },
  sheetTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "right",
    writingDirection: "rtl",
  },
  sourceText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "right",
    writingDirection: "rtl",
  },
  summaryLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  summaryRow: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    flexDirection: "row-reverse",
    justifyContent: "space-between",
    padding: fiticianTokens.spacing[3],
  },
  summaryValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "left",
    writingDirection: "rtl",
  },
});
