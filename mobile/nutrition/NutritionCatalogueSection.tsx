import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { nutritionKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import {
  AppIcon,
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
import { RTL_LAYOUT, RTL_ROW, RTL_TEXT } from "../ui/rtl";
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
  formatCatalogueDisplayNumber,
  mealCatalogueCategoryLabel,
  selectDefaultFoodPortion,
} from "./nutritionCatalogueModel";
import { NutritionThumbnail } from "./NutritionThumbnail";

type CatalogueMode = "foods" | "meals";

const MEAL_CATEGORY_ORDER: readonly MealCatalogueCategory[] = [
  "breakfast",
  "lunch",
  "post_workout",
  "snack",
  "dinner",
];

const mealCatalogueRoleLabels: Readonly<Record<string, string>> = {
  carbohydrate: "کربوهیدرات",
  fat: "چربی",
  fibre: "فیبر",
  flavor_profile: "طعم و چاشنی",
  micronutrient_source: "ریزمغذی‌ها",
  none: "بدون نقش",
  primary_carb: "کربوهیدرات اصلی",
  primary_fat: "چربی اصلی",
  primary_protein: "پروتئین اصلی",
  protein: "پروتئین",
  vegetable_volume: "حجم سبزیجات",
};

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
      {mode === "meals" && dedicatedMode ? (
        <MealCatalogueHero />
      ) : mode === "foods" ? (
        <PageHeading
          eyebrow={dedicatedMode ? "تغذیه · کاتالوگ" : "تغذیه"}
          supportingText="مواد غذایی تأییدشده را جست‌وجو کن و جزئیات هر مورد را ببین."
          title="کاتالوگ مواد غذایی"
        />
      ) : (
        <PageHeading
          eyebrow={dedicatedMode ? "تغذیه · کاتالوگ" : "تغذیه"}
          supportingText="وعده‌های منتشرشده و مواد تشکیل‌دهنده قابل نمایش را مرور کن."
          title="کاتالوگ وعده‌ها"
        />
      )}
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
          page={mealPage}
          state={mealState}
        />
      )}
      <FoodDetailsSheet food={selectedFood} onClose={() => setSelectedFood(null)} />
    </View>
  );
}

function MealCatalogueHero() {
  return (
    <View style={[styles.mealHero, RTL_LAYOUT]}>
      <Text style={[styles.mealHeroEyebrow, RTL_TEXT]}>ترکیب‌های کنترل‌شده تغذیه</Text>
      <Text accessibilityRole="header" style={[styles.mealHeroTitle, RTL_TEXT]}>کاتالوگ وعده‌های غذایی</Text>
      <Text style={[styles.mealHeroDescription, RTL_TEXT]}>
        ترکیب معتبر هر وعده و بازه مجاز مواد غذایی را مشاهده کنید. مقدار نهایی را موتور تغذیه تعیین می‌کند.
      </Text>
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
  page,
  state,
}: {
  readonly category: MealCatalogueCategory | null;
  readonly onCategoryChange: (category: MealCatalogueCategory | null) => void;
  readonly onRetry: () => void;
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
    <View style={styles.mealCatalogueStack}>
      <MealCategoryFilter category={category} onCategoryChange={onCategoryChange} />
      {page.items.length === 0 ? (
        <EmptyState title="در این دسته وعده‌ای ثبت نشده است">دسته‌بندی دیگری را انتخاب کن.</EmptyState>
      ) : (
        <View style={styles.mealCardStack}>
          {page.items.map((meal) => (
            <MealCatalogueCard
              key={meal.id}
              meal={meal}
            />
          ))}
        </View>
      )}
    </View>
  );
}

function FoodCatalogueCard({ food, onPress }: { readonly food: FoodCatalogueItem; readonly onPress: () => void }) {
  const defaultPortion = selectDefaultFoodPortion(food);
  return (
    <Card onPress={onPress} style={styles.catalogueCard} variant="interactive">
      <View style={styles.catalogueIdentity}>
        <View style={styles.cardHeading}>
          <View style={styles.cardCopy}>
            <Text style={styles.cardTitle}>{food.name_fa}</Text>
            <Text style={styles.cardEnglish}>{food.name_en}</Text>
          </View>
          <Text style={styles.category}>{foodCatalogueCategoryLabel(food.category)}</Text>
        </View>
        <NutritionThumbnail imageUrl={food.image_url} name={food.name_fa} shape="circle" style={styles.catalogueThumbnail} />
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

function MealCategoryFilter({
  category,
  onCategoryChange,
}: {
  readonly category: MealCatalogueCategory | null;
  readonly onCategoryChange: (category: MealCatalogueCategory | null) => void;
}) {
  return (
    <View style={styles.mealFilter}>
      <Text style={[styles.mealFilterLabel, RTL_TEXT]}>دسته‌بندی وعده‌ها:</Text>
      <ScrollView
        contentContainerStyle={[styles.mealChipRow, RTL_ROW]}
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.mealChipScroller}
      >
        <MealChip label="همه" onPress={() => onCategoryChange(null)} selected={category === null} />
        {MEAL_CATEGORY_ORDER.map((value) => (
          <MealChip
            key={value}
            label={mealCatalogueCategoryLabel(value)}
            onPress={() => onCategoryChange(value)}
            selected={category === value}
          />
        ))}
      </ScrollView>
    </View>
  );
}

function MealChip({
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
      style={[styles.mealChip, selected && styles.mealChipSelected]}
    >
      <Text style={[styles.mealChipText, selected && styles.mealChipTextSelected, RTL_TEXT]}>{label}</Text>
    </Pressable>
  );
}

function MealCatalogueCard({
  meal,
}: {
  readonly meal: MealCatalogueItem;
}) {
  const [expanded, setExpanded] = useState(false);
  const statusContainerStyle = meal.verification_status === "verified"
    ? styles.mealStatusVerified
    : meal.verification_status === "draft"
      ? styles.mealStatusDraft
      : styles.mealStatusRetired;
  const statusTextStyle = meal.verification_status === "verified"
    ? styles.mealStatusVerifiedText
    : meal.verification_status === "draft"
      ? styles.mealStatusDraftText
      : styles.mealStatusRetiredText;

  return (
    <View style={[styles.mealCard, RTL_LAYOUT]} testID={`meal-card-${meal.id}`}>
      <Pressable
        accessibilityLabel={meal.name_fa}
        accessibilityRole="button"
        accessibilityState={{ expanded }}
        onPress={() => setExpanded((current) => !current)}
        style={[styles.mealSummary, RTL_ROW]}
        testID={`meal-card-${meal.id}-summary`}
      >
        <View style={[styles.mealIdentity, RTL_ROW]}>
          <NutritionThumbnail imageUrl={meal.image_url} name={meal.name_fa} style={styles.mealImage} />
          <View style={styles.mealCopy}>
            <Text style={[styles.mealCode, RTL_TEXT]}>
              {meal.code} · {mealCatalogueCategoryLabel(meal.category)}
            </Text>
            <Text style={[styles.mealTitle, RTL_TEXT]}>{meal.name_fa}</Text>
          </View>
        </View>
        <View style={[styles.mealStatus, statusContainerStyle]}>
          <Text style={[styles.mealStatusText, statusTextStyle, RTL_TEXT]}>
            {mealStatusLabel(meal.verification_status)}
          </Text>
        </View>
        <View style={styles.mealDisclosureIcon}>
          <AppIcon color={fiticianTokens.colors.aqua} name={expanded ? "chevronUp" : "chevronDown"} size={fiticianTokens.iconSize.md} />
        </View>
      </Pressable>
      {expanded ? (
        <View style={[styles.mealDetails, RTL_LAYOUT]}>
          <View style={styles.mealIngredientStack}>
            {meal.items.map((item) => (
              <MealIngredientRow item={item} key={item.food_id} />
            ))}
          </View>
          <Text style={[styles.mealReferenceNote, RTL_TEXT]}>
            مقادیر نهایی داخل این بازه توسط planner تعیین می‌شوند.
          </Text>
        </View>
      ) : null}
    </View>
  );
}

function MealIngredientRow({ item }: { readonly item: MealCatalogueItem["items"][number] }) {
  return (
    <View style={[styles.mealIngredient, RTL_LAYOUT]}>
      <Text style={[styles.mealIngredientName, RTL_TEXT]}>{item.food_name_fa}</Text>
      <Text style={[styles.mealIngredientRole, RTL_TEXT]}>{mealCatalogueRoleLabel(item.functional_role)}</Text>
      <View style={[styles.mealIngredientMeta, RTL_ROW]}>
        <Text style={[styles.mealIngredientMetaText, RTL_TEXT]}>
          {formatCatalogueDisplayNumber(item.min_grams, 1)} تا {formatCatalogueDisplayNumber(item.max_grams, 1)} گرم
        </Text>
        <Text style={[styles.mealIngredientMetaText, RTL_TEXT]}>
          {item.is_required ? "الزامی" : "اختیاری"}
        </Text>
      </View>
    </View>
  );
}

function mealCatalogueRoleLabel(role: string | null): string {
  return role === null ? mealCatalogueRoleLabels.none : mealCatalogueRoleLabels[role] ?? role;
}

function mealStatusLabel(status: MealCatalogueItem["verification_status"]): string {
  switch (status) {
    case "draft":
      return "پیش‌نویس";
    case "verified":
      return "تأییدشده";
    case "retired":
      return "بازنشسته";
  }
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
      <Text style={styles.summaryLabel}>{label}</Text>
      <Text style={styles.summaryValue}>{value}</Text>
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
  mealCard: {
    backgroundColor: "rgba(10,31,30,0.75)",
    borderColor: "rgba(234,244,241,0.12)",
    borderRadius: fiticianTokens.radii.card,
    borderTopColor: fiticianTokens.colors.aqua,
    borderTopWidth: 6,
    borderWidth: 1,
    elevation: fiticianTokens.shadows.card.elevation,
    overflow: "hidden",
    padding: 18,
    shadowColor: fiticianTokens.shadows.card.color,
    shadowOffset: fiticianTokens.shadows.card.offset,
    shadowOpacity: fiticianTokens.shadows.card.opacity,
    shadowRadius: fiticianTokens.shadows.card.radius,
  },
  mealCatalogueStack: {
    gap: fiticianTokens.spacing[4],
  },
  mealCardStack: {
    gap: fiticianTokens.spacing[4],
  },
  mealHero: {
    alignItems: "stretch",
    gap: fiticianTokens.spacing[1],
  },
  mealHeroDescription: {
    color: "rgba(232,244,241,0.78)",
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 26,
  },
  mealHeroEyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    letterSpacing: 0.4,
    lineHeight: 20,
  },
  mealHeroTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    lineHeight: 40,
  },
  mealFilter: {
    alignItems: "stretch",
    gap: fiticianTokens.spacing[2],
  },
  mealFilterLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 20,
  },
  mealChipScroller: {
    width: "100%",
  },
  mealChipRow: {
    alignItems: "center",
    gap: fiticianTokens.spacing[2],
  },
  mealChip: {
    alignItems: "center",
    backgroundColor: "rgba(10,31,30,0.65)",
    borderColor: "rgba(234,244,241,0.14)",
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    justifyContent: "center",
    minHeight: 44,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  mealChipSelected: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderColor: fiticianTokens.colors.aqua,
  },
  mealChipText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.compact,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 20,
  },
  mealChipTextSelected: {
    color: fiticianTokens.colors.canvas,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
  },
  mealSummary: {
    alignItems: "center",
    gap: fiticianTokens.spacing[3],
    width: "100%",
  },
  mealIdentity: {
    alignItems: "center",
    flex: 1,
    gap: fiticianTokens.spacing[3],
    minWidth: 0,
  },
  mealImage: {
    borderColor: "rgba(80,223,206,0.32)",
    borderRadius: 12,
    borderWidth: 1,
    flexShrink: 0,
    height: 68,
    width: 68,
  },
  mealCopy: {
    alignItems: "stretch",
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
  },
  mealCode: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 20,
  },
  mealTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.lg,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 26,
  },
  mealStatus: {
    alignItems: "center",
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    flexShrink: 0,
    justifyContent: "center",
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  mealStatusText: {
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 18,
  },
  mealStatusVerified: {
    backgroundColor: "rgba(16,185,129,0.15)",
    borderColor: "rgba(16,185,129,0.30)",
  },
  mealStatusVerifiedText: {
    color: "#10b981",
  },
  mealStatusDraft: {
    backgroundColor: "rgba(245,158,11,0.15)",
    borderColor: "rgba(245,158,11,0.30)",
  },
  mealStatusDraftText: {
    color: "#f59e0b",
  },
  mealStatusRetired: {
    backgroundColor: "rgba(148,163,184,0.15)",
    borderColor: "rgba(148,163,184,0.30)",
  },
  mealStatusRetiredText: {
    color: "#94a3b8",
  },
  mealDisclosureIcon: {
    alignItems: "center",
    flexShrink: 0,
    justifyContent: "center",
    width: 28,
  },
  mealDetails: {
    borderTopColor: "rgba(234,244,241,0.10)",
    borderTopWidth: 1,
    gap: fiticianTokens.spacing[3],
    marginTop: fiticianTokens.spacing[4],
    paddingTop: fiticianTokens.spacing[4],
  },
  mealIngredientStack: {
    gap: fiticianTokens.spacing[2],
  },
  mealIngredient: {
    alignItems: "stretch",
    backgroundColor: "rgba(6,21,20,0.55)",
    borderColor: "rgba(234,244,241,0.10)",
    borderRadius: 12,
    borderWidth: 1,
    gap: fiticianTokens.spacing[1],
    padding: fiticianTokens.spacing[3],
  },
  mealIngredientName: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 22,
  },
  mealIngredientRole: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 18,
  },
  mealIngredientMeta: {
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
    width: "100%",
  },
  mealIngredientMetaText: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 20,
  },
  mealReferenceNote: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
  },
  cardCopy: {
    alignItems: "stretch",
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
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  cardStack: {
    gap: fiticianTokens.spacing[3],
  },
  catalogueIdentity: {
    alignItems: "center",
    flexDirection: "row",
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
    textAlign: "auto",
    writingDirection: "rtl",
  },
  category: {
    color: fiticianTokens.colors.aqua,
    flexShrink: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
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
    flexDirection: "row",
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
    textAlign: "auto",
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
    textAlign: "auto",
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
    flexDirection: "row",
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
    textAlign: "auto",
    writingDirection: "rtl",
  },
  macroRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  macroValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  pageMeta: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  portionHint: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
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
    alignSelf: "flex-start",
    height: 128,
    width: 128,
  },
  sheetTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  sourceText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  summaryLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  summaryRow: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    padding: fiticianTokens.spacing[3],
  },
  summaryValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "auto",
    writingDirection: "rtl",
  },
});
