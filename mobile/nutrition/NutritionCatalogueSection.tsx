import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as ImagePicker from "expo-image-picker";
import { File } from "expo-file-system";
import { useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { Linking, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

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
import { getMobileViewState, mobileRequestErrorMessage } from "../ui/requestState";
import { RTL_LAYOUT, RTL_ROW, RTL_TEXT } from "../ui/rtl";
import { fiticianTokens } from "../ui/tokens";
import {
  createNutritionCatalogueApi,
  type AdminFoodCatalogueItem,
  type AdminFoodCataloguePage,
  type CatalogueFoodImageAsset,
  type FoodCataloguePrice,
  type FoodCataloguePage,
  type FoodCatalogueWriteInput,
  type FoodPriceOverrideInput,
  type FoodCatalogueItem,
  type NutritionCatalogueApi,
  type SingleFoodPriceResearchResponse,
  type MealCatalogueCategory,
  type MealCatalogueItem,
  catalogueFoodImageExtension,
  catalogueFoodImageMimeTypeForAsset,
} from "./nutritionCatalogueApi";
import {
  foodCatalogueBasisLabel,
  foodCatalogueCalories,
  foodCatalogueMacroRows,
  foodCatalogueCategoryLabel,
  foodCatalogueNutrientRows,
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

const FOOD_PAGE_SIZE = 24;

type CatalogueFoodItem = FoodCatalogueItem | AdminFoodCatalogueItem;
type FoodCataloguePageData = FoodCataloguePage | AdminFoodCataloguePage;
type FoodResearchState =
  | { readonly status: "researching" }
  | { readonly message: string; readonly status: "error" };

export function NutritionCatalogueSection({ initialMode }: { readonly initialMode?: CatalogueMode } = {}) {
  const auth = useMobileAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const connectivityStatus = useConnectivityStatus();
  const api = useMemo(
    () => createNutritionCatalogueApi(auth.request, auth.upload),
    [auth.request, auth.upload],
  );
  const dedicatedMode = initialMode !== undefined;
  const isAdmin = auth.user?.is_admin === true;
  const [mode, setMode] = useState<CatalogueMode>(initialMode ?? "foods");
  const [searchInput, setSearchInput] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [foodCategory, setFoodCategory] = useState("");
  const [foodPageNumber, setFoodPageNumber] = useState(1);
  const [mealCategory, setMealCategory] = useState<MealCatalogueCategory | null>(null);
  const [selectedFood, setSelectedFood] = useState<CatalogueFoodItem | null>(null);
  const [foodToPriceEdit, setFoodToPriceEdit] = useState<AdminFoodCatalogueItem | null>(null);
  const [foodToImageEdit, setFoodToImageEdit] = useState<AdminFoodCatalogueItem | null>(null);
  const [foodToDelete, setFoodToDelete] = useState<AdminFoodCatalogueItem | null>(null);
  const [showAddFood, setShowAddFood] = useState(false);
  const [researchStates, setResearchStates] = useState<Record<string, FoodResearchState>>({});
  const [pricePatches, setPricePatches] = useState<Record<string, FoodCataloguePrice>>({});
  const foodQueryKey = nutritionKeys.foodCatalogue({
    category: foodCategory,
    page: foodPageNumber,
    pageSize: FOOD_PAGE_SIZE,
    query: submittedQuery,
    scope: isAdmin ? "admin" : "member",
  });
  const foodQuery = useQuery({
    enabled: mode === "foods",
    queryFn: () => {
      const input = {
        category: foodCategory || undefined,
        page: foodPageNumber,
        pageSize: FOOD_PAGE_SIZE,
        query: submittedQuery || undefined,
      };
      return isAdmin ? api.getAdminFoodCatalogue(input) : api.getFoodCatalogue(input);
    },
    queryKey: foodQueryKey,
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

  function submitFoodSearch(): void {
    setSubmittedQuery(searchInput.trim());
    setFoodPageNumber(1);
  }

  function selectFoodCategory(category: string): void {
    setFoodCategory(category);
    setFoodPageNumber(1);
  }

  async function invalidateFoodCatalogue(): Promise<void> {
    await queryClient.invalidateQueries({ queryKey: foodQueryKey });
  }

  async function researchPrice(food: AdminFoodCatalogueItem): Promise<void> {
    if (researchStates[food.slug]?.status === "researching") return;
    setResearchStates((current) => ({ ...current, [food.slug]: { status: "researching" } }));
    try {
      const result = await api.researchFoodPrice(food.slug, true);
      const candidatePrice = result.candidate_reference_price_toman?.trim();
      const canonicalUnit = result.canonical_unit?.trim();
      const referenceUnit = canonicalUnit === undefined ? null : researchReferenceUnit(canonicalUnit);
      if (result.status !== "success" || !candidatePrice || !canonicalUnit || referenceUnit === null) {
        const fallback = result.status === "no_quotes"
          ? "قیمتی در فروشگاه‌های آنلاین برای این ماده غذایی یافت نشد."
          : "قیمت معتبر از سرویس استعلام دریافت نشد.";
        setResearchStates((current) => ({
          ...current,
          [food.slug]: {
            message: result.message?.trim() || fallback,
            status: "error",
          },
        }));
        return;
      }
      setPricePatches((current) => ({
        ...current,
        [food.slug]: {
          accepted_at: new Date().toISOString(),
          canonical_unit: canonicalUnit,
          observed_at: new Date().toISOString(),
          reference_price_irr: null,
          reference_price_toman: candidatePrice,
          reference_unit: referenceUnit,
          source: "manual_override",
          status: "accepted",
        },
      }));
      setResearchStates((current) => {
        const next = { ...current };
        delete next[food.slug];
        return next;
      });
    } catch (error) {
      setResearchStates((current) => ({
        ...current,
        [food.slug]: { message: mobileRequestErrorMessage(error, "استعلام قیمت انجام نشد."), status: "error" },
      }));
    }
  }

  async function deleteFood(food: AdminFoodCatalogueItem): Promise<void> {
    try {
      await api.deleteCatalogueFood(food.slug);
      setFoodToDelete(null);
      await invalidateFoodCatalogue();
      if (foodPage?.items.length === 1 && foodPage.page > 1) setFoodPageNumber((current) => current - 1);
    } catch {
      throw new Error("حذف ماده غذایی انجام نشد.");
    }
  }

  function clearPricePatch(slug: string): void {
    setPricePatches((current) => {
      const next = { ...current };
      delete next[slug];
      return next;
    });
  }

  return (
    <View style={styles.section}>
      {mode === "meals" && dedicatedMode ? (
        <MealCatalogueHero />
      ) : mode === "foods" ? (
        dedicatedMode ? <FoodCatalogueHero onBack={() => router.push("/member/nutrition")} /> : (
          <PageHeading
            eyebrow="تغذیه"
            supportingText="مواد غذایی تأییدشده را جست‌وجو کن و جزئیات هر مورد را ببین."
            title="کاتالوگ مواد غذایی"
          />
        )
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
          isAdmin={isAdmin}
          onAdd={() => setShowAddFood(true)}
          onCategoryChange={selectFoodCategory}
          onDelete={setFoodToDelete}
          onImageEdit={setFoodToImageEdit}
          onPageChange={setFoodPageNumber}
          onPriceEdit={setFoodToPriceEdit}
          onRetry={() => void foodQuery.refetch()}
          onSearchInput={setSearchInput}
          onSelect={setSelectedFood}
          onSearchSubmit={submitFoodSearch}
          onResearch={(food) => void researchPrice(food)}
          page={foodPage}
          pricePatches={pricePatches}
          researchStates={researchStates}
          searchInput={searchInput}
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
      <FoodDetailsSheet key={selectedFood?.id ?? "none"} food={selectedFood} onClose={() => setSelectedFood(null)} />
      {isAdmin ? (
        <>
          <AddFoodSheet
            api={api}
            key={`add-food-sheet-${showAddFood ? "open" : "closed"}`}
            onClose={() => setShowAddFood(false)}
            onSaved={() => {
              setShowAddFood(false);
              void invalidateFoodCatalogue();
            }}
            visible={showAddFood}
          />
          <FoodImageSheet
            api={api}
            food={foodToImageEdit}
            key={`image-food-sheet-${foodToImageEdit?.id ?? "closed"}`}
            onClose={() => setFoodToImageEdit(null)}
            onSaved={() => {
              setFoodToImageEdit(null);
              void invalidateFoodCatalogue();
            }}
          />
          <PriceOverrideSheet
            api={api}
            food={foodToPriceEdit}
            key={`price-food-sheet-${foodToPriceEdit?.id ?? "closed"}`}
            onClose={() => setFoodToPriceEdit(null)}
            onSaved={() => {
              if (foodToPriceEdit) clearPricePatch(foodToPriceEdit.slug);
              setFoodToPriceEdit(null);
              void invalidateFoodCatalogue();
            }}
          />
          <DeleteFoodSheet
            food={foodToDelete}
            key={`delete-food-sheet-${foodToDelete?.id ?? "closed"}`}
            onClose={() => setFoodToDelete(null)}
            onDelete={deleteFood}
          />
        </>
      ) : null}
    </View>
  );
}

function FoodCatalogueHero({ onBack }: { readonly onBack: () => void }) {
  return (
    <View style={[styles.foodHero, RTL_ROW]}>
      <Text accessibilityRole="header" style={[styles.foodHeroTitle, RTL_TEXT]}>کاتالوگ مواد غذایی</Text>
      <Pressable accessibilityRole="button" onPress={onBack} style={styles.foodBackButton}>
        <Text style={[styles.foodBackButtonText, RTL_TEXT]}>تغذیه</Text>
      </Pressable>
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
  isAdmin,
  onAdd,
  onCategoryChange,
  onDelete,
  onImageEdit,
  onPageChange,
  onPriceEdit,
  onRetry,
  onResearch,
  onSearchInput,
  onSearchSubmit,
  onSelect,
  page,
  pricePatches,
  researchStates,
  searchInput,
  state,
}: {
  readonly category: string;
  readonly isAdmin: boolean;
  readonly onAdd: () => void;
  readonly onCategoryChange: (category: string) => void;
  readonly onDelete: (food: AdminFoodCatalogueItem) => void;
  readonly onImageEdit: (food: AdminFoodCatalogueItem) => void;
  readonly onPageChange: (page: number) => void;
  readonly onPriceEdit: (food: AdminFoodCatalogueItem) => void;
  readonly onRetry: () => void;
  readonly onResearch: (food: AdminFoodCatalogueItem) => void;
  readonly onSearchInput: (query: string) => void;
  readonly onSearchSubmit: () => void;
  readonly onSelect: (food: CatalogueFoodItem) => void;
  readonly page: ReturnType<typeof stateData<FoodCataloguePageData>>;
  readonly pricePatches: Record<string, FoodCataloguePrice>;
  readonly researchStates: Record<string, FoodResearchState>;
  readonly searchInput: string;
  readonly state: ReturnType<typeof getMobileViewState<FoodCataloguePageData>>;
}) {
  if (state.status === "loading" && page === undefined) {
    return (
      <View style={styles.foodCatalogueStack}>
        <FoodCatalogueToolbar
          category={category}
          categories={[]}
          isAdmin={isAdmin}
          onAdd={onAdd}
          onCategoryChange={onCategoryChange}
          onSearchInput={onSearchInput}
          onSearchSubmit={onSearchSubmit}
          searchInput={searchInput}
        />
        <Skeleton height={420} />
      </View>
    );
  }
  if (state.status === "error" && page === undefined) {
    return (
      <View style={styles.foodCatalogueStack}>
        <FoodCatalogueToolbar
          category={category}
          categories={[]}
          isAdmin={isAdmin}
          onAdd={onAdd}
          onCategoryChange={onCategoryChange}
          onSearchInput={onSearchInput}
          onSearchSubmit={onSearchSubmit}
          searchInput={searchInput}
        />
        <Notice actionLabel="تلاش دوباره" message="کاتالوگ مواد غذایی دریافت نشد." onAction={onRetry} variant="danger" />
      </View>
    );
  }
  if (state.status === "offline" && page === undefined) {
    return (
      <View style={styles.foodCatalogueStack}>
        <FoodCatalogueToolbar
          category={category}
          categories={[]}
          isAdmin={isAdmin}
          onAdd={onAdd}
          onCategoryChange={onCategoryChange}
          onSearchInput={onSearchInput}
          onSearchSubmit={onSearchSubmit}
          searchInput={searchInput}
        />
        <Notice message="برای مرور کاتالوگ مواد غذایی به اینترنت وصل شو." variant="offline" />
      </View>
    );
  }
  if (page === undefined) return null;
  const pageCount = Math.max(1, Math.ceil(page.total / page.page_size));

  return (
    <View style={styles.foodCatalogueStack}>
      <FoodCatalogueToolbar
        category={category}
        categories={page.categories}
        isAdmin={isAdmin}
        onAdd={onAdd}
        onCategoryChange={onCategoryChange}
        onSearchInput={onSearchInput}
        onSearchSubmit={onSearchSubmit}
        searchInput={searchInput}
      />
      {state.status === "offline" || state.status === "stale" ? (
        <Notice compact message="نتایج کاتالوگ تازه‌سازی نشده‌اند." variant="offline" />
      ) : null}
      {page.items.length === 0 ? (
        <EmptyState title="ماده غذایی پیدا نشد">عبارت جستجو یا دسته‌بندی را تغییر بده.</EmptyState>
      ) : (
        <View style={styles.cardStack}>
          {page.items.map((food) => (
            <FoodCatalogueCard
              food={food}
              isAdmin={isAdmin}
              key={food.id}
              onDelete={onDelete}
              onDetails={() => onSelect(food)}
              onImageEdit={onImageEdit}
              onPriceEdit={onPriceEdit}
              onResearch={onResearch}
              price={isAdmin ? pricePatches[food.slug] ?? (food as AdminFoodCatalogueItem).price : undefined}
              researchState={researchStates[food.slug]}
            />
          ))}
        </View>
      )}
      {pageCount > 1 ? (
        <FoodPagination
          onNext={() => onPageChange(page.page + 1)}
          onPrevious={() => onPageChange(page.page - 1)}
          page={page.page}
          pageCount={pageCount}
        />
      ) : null}
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

function FoodCatalogueCard({
  food,
  isAdmin,
  onDelete,
  onDetails,
  onImageEdit,
  onPriceEdit,
  onResearch,
  price,
  researchState,
}: {
  readonly food: CatalogueFoodItem;
  readonly isAdmin: boolean;
  readonly onDelete: (food: AdminFoodCatalogueItem) => void;
  readonly onDetails: () => void;
  readonly onImageEdit: (food: AdminFoodCatalogueItem) => void;
  readonly onPriceEdit: (food: AdminFoodCatalogueItem) => void;
  readonly onResearch: (food: AdminFoodCatalogueItem) => void;
  readonly price?: FoodCataloguePrice;
  readonly researchState?: FoodResearchState;
}) {
  const defaultPortion = selectDefaultFoodPortion(food);
  const calories = foodCatalogueCalories(food);
  const adminFood = isAdmin
    ? { ...food as AdminFoodCatalogueItem, price: price ?? (food as AdminFoodCatalogueItem).price }
    : null;
  return (
    <Card direction="ltr" style={styles.foodCard} testID={`food-card-${food.id}`} variant="interactive">
      <View style={styles.foodCardIdentity}>
        <NutritionThumbnail
          imageUrl={food.image_url}
          name={food.name_fa}
          shape="circle"
          style={styles.foodThumbnail}
        />
        <View style={styles.foodCardCopy}>
          <View style={styles.foodCardTitleRow}>
            <View style={styles.foodCardNames}>
              <Text style={[styles.foodCardCategory, RTL_TEXT]}>{foodCatalogueCategoryLabel(food.category)}</Text>
              <Text style={[styles.foodCardTitle, RTL_TEXT]}>{food.name_fa}</Text>
              <Text style={styles.foodCardEnglish}>{food.name_en}</Text>
            </View>
            <View style={styles.foodCalories}>
              <Text style={styles.foodCaloriesValue}>{calories.value === "—" ? calories.value : `${calories.value} ${calories.unit}`}</Text>
              <Text style={[styles.foodCaloriesLabel, RTL_TEXT]}>{calories.label}</Text>
            </View>
          </View>
          <Text style={[styles.foodBasis, RTL_TEXT]}>{foodCatalogueBasisLabel(defaultPortion)}</Text>
        </View>
      </View>
      {isAdmin ? (
        <FoodPriceTicket
          foodSlug={food.slug}
          price={price}
          researchState={researchState}
        />
      ) : null}
      <View style={styles.foodMacroStrip} testID={`food-macro-strip-${food.id}`}>
        {foodCatalogueMacroRows(food).map((macro, index) => (
          <View
            key={macro.code}
            style={[styles.foodMacroCell, index > 0 && styles.foodMacroCellDivider]}
          >
            <Text style={styles.foodMacroValue}>{macro.value === "—" ? macro.value : `${macro.value} گرم`}</Text>
            <Text style={[styles.foodMacroLabel, RTL_TEXT]}>{macro.label}</Text>
          </View>
        ))}
      </View>
      <View style={styles.foodActions}>
        <FoodActionButton label="جزئیات بیشتر" onPress={onDetails} />
        {adminFood ? (
          <>
            <FoodActionButton
              label={food.image_url ? "جایگزینی تصویر" : "بارگذاری تصویر"}
              onPress={() => onImageEdit(adminFood)}
            />
            <FoodActionButton label="ویرایش قیمت" onPress={() => onPriceEdit(adminFood)} />
            <FoodActionButton
              busy={researchState?.status === "researching"}
              label={researchState?.status === "researching" ? "در حال استعلام…" : "استعلام قیمت"}
              onPress={() => onResearch(adminFood)}
              variant="amber"
            />
            <FoodActionButton label="حذف" onPress={() => onDelete(adminFood)} variant="danger" />
          </>
        ) : null}
      </View>
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

function FoodDetailsSheet({ food, onClose }: { readonly food: CatalogueFoodItem | null; readonly onClose: () => void }) {
  const [commonPortionSelected, setCommonPortionSelected] = useState(true);

  const defaultPortion = food === null ? null : selectDefaultFoodPortion(food);
  const selectedPortion = commonPortionSelected ? defaultPortion : null;

  return (
    <Sheet onClose={onClose} title={food?.name_fa ?? "جزئیات ماده غذایی"} visible={food !== null}>
      {food ? (
        <View style={styles.sheetStack}>
          <Text style={[styles.foodCardCategory, RTL_TEXT]}>ریز‌مغذی‌ها</Text>
          <Text style={styles.foodCardEnglish}>{food.name_en}</Text>
          {food.portions.length > 0 ? (
            <View style={styles.detailStack}>
              <Text style={[styles.sheetLabel, RTL_TEXT]}>واحد معمول</Text>
              <View style={[styles.basisChoices, RTL_ROW]}>
                <BasisChoice
                  label={defaultPortion?.label_fa ?? "واحد معمول"}
                  onPress={() => setCommonPortionSelected(true)}
                  selected={commonPortionSelected}
                />
                <BasisChoice
                  label="۱۰۰ گرم"
                  onPress={() => setCommonPortionSelected(false)}
                  selected={!commonPortionSelected}
                />
              </View>
            </View>
          ) : null}
          <Text style={[styles.foodBasis, RTL_TEXT]}>
            {foodCatalogueBasisLabel(selectedPortion)}
            {selectedPortion ? ` · ${selectedPortion.label_fa} ≈ ${formatCatalogueDisplayNumber(selectedPortion.grams, 0)} گرم` : ""}
          </Text>
          <Text style={[styles.sheetTitle, RTL_TEXT]}>همه مواد مغذی</Text>
          <View style={styles.detailStack}>
            {foodCatalogueNutrientRows(food, selectedPortion).map((nutrient) => (
              <SummaryRow
                key={nutrient.code}
                label={nutrient.label}
                value={`${nutrient.value} ${nutrient.unit}`}
              />
            ))}
          </View>
          {food.allergen_tags && food.allergen_tags.length > 0 ? (
            <View style={styles.detailStack}>
              <Text style={[styles.sheetLabel, RTL_TEXT]}>آلرژن‌ها</Text>
              <Text style={[styles.sourceText, RTL_TEXT]}>{food.allergen_tags.join("، ")}</Text>
            </View>
          ) : null}
          <Text style={styles.sourceText}>منبع: {food.source.name}</Text>
          <Button
            label="مشاهده منبع"
            onPress={() => void Linking.openURL(food.source.reference).catch(() => undefined)}
            variant="ghost"
          />
          <Button label="بستن" onPress={onClose} variant="ghost" />
        </View>
      ) : null}
    </Sheet>
  );
}

function FoodCatalogueToolbar({
  category,
  categories,
  isAdmin,
  onAdd,
  onCategoryChange,
  onSearchInput,
  onSearchSubmit,
  searchInput,
}: {
  readonly category: string;
  readonly categories: readonly string[];
  readonly isAdmin: boolean;
  readonly onAdd: () => void;
  readonly onCategoryChange: (category: string) => void;
  readonly onSearchInput: (value: string) => void;
  readonly onSearchSubmit: () => void;
  readonly searchInput: string;
}) {
  return (
    <View style={styles.foodToolbar}>
      <View style={[styles.foodSearchRow, RTL_LAYOUT]} testID="food-search-row">
        <TextInput
          accessibilityLabel="جستجوی مواد غذایی"
          onChangeText={onSearchInput}
          onSubmitEditing={onSearchSubmit}
          placeholder="مثلاً عدس یا سینه مرغ"
          placeholderTextColor={fiticianTokens.colors.muted}
          returnKeyType="search"
          style={[styles.foodSearchInput, RTL_TEXT]}
          value={searchInput}
        />
        <Pressable accessibilityRole="button" onPress={onSearchSubmit} style={styles.foodSearchButton}>
          <Text style={styles.foodSearchButtonText}>جست‌وجو</Text>
        </Pressable>
      </View>
      {isAdmin ? (
        <Pressable accessibilityRole="button" onPress={onAdd} style={styles.foodAddButton}>
          <Text style={styles.foodAddButtonText}>+ افزودن ماده غذایی</Text>
        </Pressable>
      ) : null}
      <ScrollView
        contentContainerStyle={[styles.foodChipRow, RTL_ROW]}
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.foodChipScroller}
        testID="food-category-scroll"
      >
        <FoodCategoryChip
          label="همه گروه‌ها"
          onPress={() => onCategoryChange("")}
          selected={category === ""}
        />
        {categories.map((value) => (
          <FoodCategoryChip
            key={value}
            label={foodCatalogueCategoryLabel(value)}
            onPress={() => onCategoryChange(value)}
            selected={category === value}
          />
        ))}
      </ScrollView>
    </View>
  );
}

function FoodCategoryChip({ label, onPress, selected }: { readonly label: string; readonly onPress: () => void; readonly selected: boolean }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={[styles.foodChip, selected && styles.foodChipSelected]}
    >
      <Text style={[styles.foodChipText, selected && styles.foodChipTextSelected, RTL_TEXT]}>{label}</Text>
    </Pressable>
  );
}

function FoodPagination({
  onNext,
  onPrevious,
  page,
  pageCount,
}: {
  readonly onNext: () => void;
  readonly onPrevious: () => void;
  readonly page: number;
  readonly pageCount: number;
}) {
  return (
    <View style={[styles.foodPagination, RTL_ROW]}>
      <FoodActionButton disabled={page === 1} label="قبلی" onPress={onPrevious} />
      <Text style={[styles.foodPaginationText, RTL_TEXT]}>
        {formatCatalogueDisplayNumber(page, 0)} / {formatCatalogueDisplayNumber(pageCount, 0)}
      </Text>
      <FoodActionButton disabled={page === pageCount} label="بعدی" onPress={onNext} />
    </View>
  );
}

function FoodActionButton({
  busy = false,
  disabled = false,
  label,
  onPress,
  variant = "default",
}: {
  readonly busy?: boolean;
  readonly disabled?: boolean;
  readonly label: string;
  readonly onPress: () => void;
  readonly variant?: "amber" | "danger" | "default";
}) {
  const unavailable = disabled || busy;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: unavailable, busy }}
      disabled={unavailable}
      onPress={onPress}
      style={[styles.foodActionButton, variant === "amber" && styles.foodActionAmber, variant === "danger" && styles.foodActionDanger, unavailable && styles.foodActionDisabled]}
    >
      <Text style={[styles.foodActionText, variant === "amber" && styles.foodActionAmberText, variant === "danger" && styles.foodActionDangerText, RTL_TEXT]}>{label}</Text>
    </Pressable>
  );
}

function FoodPriceTicket({
  foodSlug,
  price,
  researchState,
}: {
  readonly foodSlug: string;
  readonly price?: FoodCataloguePrice;
  readonly researchState?: FoodResearchState;
}) {
  const isResearching = researchState?.status === "researching";
  const hasResearchError = researchState?.status === "error";
  const displayPrice = price === undefined ? null : priceInToman(price);
  const accepted = price?.status === "accepted" && displayPrice !== null;
  return (
    <View
      accessibilityLiveRegion="polite"
      style={[
        styles.foodPriceTicket,
        !accepted && !isResearching && !hasResearchError && styles.foodPriceMissing,
        isResearching && styles.foodPriceTicketResearching,
        hasResearchError && styles.foodPriceTicketError,
      ]}
      testID={`food-price-ticket-${foodSlug}`}
    >
      <Text style={styles.foodPriceTitle}>{isResearching ? "وضعیت استعلام" : "قیمت این هفته"}</Text>
      <Text style={styles.foodPriceValue}>
        {isResearching
          ? "در حال استعلام…"
          : accepted && displayPrice !== null
            ? `${formatCatalogueDisplayNumber(displayPrice, 0)} تومان`
            : "یافت نشد"}
      </Text>
      {accepted && price?.reference_unit ? <Text style={styles.foodPriceUnit}>{foodPriceUnitLabel(price)}</Text> : null}
      {accepted && price ? <Text style={styles.foodPriceMeta}>{foodPriceSourceLabel(price)}{foodPriceDate(price.observed_at) ? ` · ${foodPriceDate(price.observed_at)}` : ""}</Text> : null}
      {researchState?.status === "error" ? <Text style={styles.foodPriceError}>{researchState.message}</Text> : null}
    </View>
  );
}

function priceInToman(price: FoodCataloguePrice): number | null {
  if (price.reference_price_toman !== null && price.reference_price_toman !== undefined) {
    const toman = Number(price.reference_price_toman);
    return Number.isFinite(toman) ? toman : null;
  }
  if (price.reference_price_irr !== null && price.reference_price_irr !== undefined) {
    const toman = Number(price.reference_price_irr) / 10;
    return Number.isFinite(toman) ? toman : null;
  }
  return null;
}

function foodPriceUnitLabel(price: FoodCataloguePrice): string {
  switch (price.reference_unit) {
    case "IRR_PER_LITER":
      return "تومان برای هر لیتر";
    case "IRR_PER_UNIT":
      return "تومان برای هر عدد";
    case "IRR_PER_KG":
    default:
      return "تومان برای هر کیلوگرم";
  }
}

function foodPriceSourceLabel(price: FoodCataloguePrice): string {
  return price.source === "manual_override" ? "جایگزین موقت ادمین" : "به‌روزرسانی خودکار بازار";
}

function foodPriceDate(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "" : new Intl.DateTimeFormat("fa-IR", { dateStyle: "short" }).format(date);
}

function researchReferenceUnit(value: string): NonNullable<FoodCataloguePrice["reference_unit"]> | null {
  if (value === "TOMAN_PER_LITER" || value === "IRR_PER_LITER") return "IRR_PER_LITER";
  if (value === "TOMAN_PER_UNIT" || value === "IRR_PER_UNIT") return "IRR_PER_UNIT";
  if (value === "TOMAN_PER_KG" || value === "IRR_PER_KG") return "IRR_PER_KG";
  return null;
}

const PRIMARY_NUTRIENTS = [
  { code: "energy_kcal", label: "کالری", unit: "kcal" },
  { code: "protein_g", label: "پروتئین", unit: "g" },
  { code: "carbohydrate_g", label: "کربوهیدرات", unit: "g" },
  { code: "total_fat_g", label: "چربی", unit: "g" },
  { code: "fibre_g", label: "فیبر", unit: "g" },
] as const;

type PrimaryNutrientCode = (typeof PRIMARY_NUTRIENTS)[number]["code"];

function AddFoodSheet({
  api,
  onClose,
  onSaved,
  visible,
}: {
  readonly api: NutritionCatalogueApi;
  readonly onClose: () => void;
  readonly onSaved: () => void;
  readonly visible: boolean;
}) {
  const [identity, setIdentity] = useState({
    category: "",
    name_en: "",
    name_fa: "",
    slug: "",
    source_name: "",
    source_reference: "",
  });
  const [values, setValues] = useState<Record<PrimaryNutrientCode, string>>({
    carbohydrate_g: "",
    energy_kcal: "",
    fibre_g: "",
    protein_g: "",
    total_fat_g: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(): Promise<void> {
    const hasMissingIdentity = Object.values(identity).some((value) => value.trim().length === 0);
    const hasInvalidNutrients = PRIMARY_NUTRIENTS.some(({ code }) => {
      const rawValue = values[code].trim();
      const numericValue = Number(rawValue);
      return rawValue.length === 0 || !Number.isFinite(numericValue) || numericValue < 0;
    });
    if (hasMissingIdentity || hasInvalidNutrients) {
      setError("مشخصات و پنج مقدار اصلی را کامل و معتبر وارد کن.");
      return;
    }

    setError(null);
    setSaving(true);
    const nutrientUnits = Object.fromEntries(PRIMARY_NUTRIENTS.map(({ code, unit }) => [code, unit]));
    const payload: FoodCatalogueWriteInput = {
      ...identity,
      aliases: [],
      canonical_quantity: 100,
      canonical_unit: "g",
      data_version: "admin-verified-v1",
      dietary_patterns: ["omnivore", "vegetarian", "vegan"],
      edible_portion: 1,
      measurement_basis: "as_purchased",
      nutrients: PRIMARY_NUTRIENTS.map(({ code }) => ({
        confidence: "high",
        nutrient_code: code,
        source_name: identity.source_name,
        source_reference: identity.source_reference,
        unit: nutrientUnits[code] ?? "g",
        unit_form: "nutrient_mass",
        value_per_100g: Number(values[code]),
      })),
      roles: ["flexible"],
      source_access_date: new Date().toISOString().slice(0, 10),
      source_food_id: null,
      verification_status: "verified",
    };
    try {
      await api.saveCatalogueFood(payload);
      onSaved();
    } catch (requestError) {
      setError(mobileRequestErrorMessage(requestError, "ماده غذایی ذخیره نشد."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet onClose={onClose} title="ماده غذایی تأییدشده" visible={visible}>
      <View style={styles.sheetStack}>
        <Text style={[styles.sheetHelper, RTL_TEXT]}>برای انتشار، مشخصات و پنج مقدار اصلی باید کامل باشند.</Text>
        <TextField
          label="شناسه انگلیسی"
          onChangeText={(value) => setIdentity((current) => ({ ...current, slug: value }))}
          required
          textDirection="ltr"
          value={identity.slug}
        />
        <TextField
          label="نام فارسی"
          onChangeText={(value) => setIdentity((current) => ({ ...current, name_fa: value }))}
          required
          value={identity.name_fa}
        />
        <TextField
          label="نام انگلیسی"
          onChangeText={(value) => setIdentity((current) => ({ ...current, name_en: value }))}
          required
          textDirection="ltr"
          value={identity.name_en}
        />
        <TextField
          label="گروه غذایی"
          onChangeText={(value) => setIdentity((current) => ({ ...current, category: value }))}
          required
          textDirection="ltr"
          value={identity.category}
        />
        <TextField
          label="نام منبع"
          onChangeText={(value) => setIdentity((current) => ({ ...current, source_name: value }))}
          required
          value={identity.source_name}
        />
        <TextField
          keyboardType="url"
          label="لینک منبع"
          onChangeText={(value) => setIdentity((current) => ({ ...current, source_reference: value }))}
          required
          textDirection="ltr"
          value={identity.source_reference}
        />
        {PRIMARY_NUTRIENTS.map(({ code, label, unit }) => (
          <TextField
            key={code}
            keyboardType="decimal-pad"
            label={`${label} (${unit})`}
            onChangeText={(value) => setValues((current) => ({ ...current, [code]: value }))}
            required
            textDirection="ltr"
            value={values[code]}
          />
        ))}
        {error ? <Notice compact message={error} variant="danger" /> : null}
        <Button
          disabled={saving}
          label={saving ? "در حال ذخیره…" : "افزودن به کاتالوگ"}
          loading={saving}
          onPress={() => void submit()}
        />
      </View>
    </Sheet>
  );
}

function FoodImageSheet({
  api,
  food,
  onClose,
  onSaved,
}: {
  readonly api: import("./nutritionCatalogueApi").NutritionCatalogueApi;
  readonly food: AdminFoodCatalogueItem | null;
  readonly onClose: () => void;
  readonly onSaved: () => void;
}) {
  const [asset, setAsset] = useState<CatalogueFoodImageAsset | null>(null);
  const [filename, setFilename] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function chooseImage(): Promise<void> {
    setError(null);
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        allowsEditing: false,
        base64: false,
        exif: false,
        mediaTypes: ["images"],
      });
      if (result.canceled) return;
      const picked = result.assets[0];
      if (picked === undefined) return;
      const mimeType = catalogueFoodImageMimeTypeForAsset(picked.mimeType, picked.uri);
      if (mimeType === null) {
        setError("فرمت تصویر پشتیبانی نمی‌شود. JPEG، PNG، WebP یا GIF انتخاب کن.");
        return;
      }
      const file = new File(picked.uri);
      if (!file.exists) {
        setError("تصویر انتخاب‌شده در دسترس نیست.");
        return;
      }
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (bytes.byteLength === 0) {
        setError("تصویر انتخاب‌شده خالی است.");
        return;
      }
      const selectedName = picked.fileName?.trim() || `food-image.${catalogueFoodImageExtension(mimeType)}`;
      setAsset({ bytes, filename: selectedName, mimeType });
      setFilename(selectedName);
    } catch (pickerError) {
      setError(mobileRequestErrorMessage(pickerError, "انتخاب تصویر انجام نشد."));
    }
  }

  async function submit(): Promise<void> {
    if (food === null || asset === null) return;
    setError(null);
    setSaving(true);
    try {
      await api.uploadCatalogueFoodImage(food.slug, asset);
      onSaved();
    } catch (requestError) {
      setError(mobileRequestErrorMessage(requestError, "تصویر ذخیره نشد."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet
      onClose={onClose}
      title={food?.image_url ? "جایگزینی تصویر غذا" : "بارگذاری تصویر غذا"}
      visible={food !== null}
    >
      <View style={styles.sheetStack}>
        <Text style={[styles.sheetHelper, RTL_TEXT]}>فایل JPEG، PNG، WebP یا GIF انتخاب کنید.</Text>
        <Button label="انتخاب تصویر" onPress={() => void chooseImage()} variant="secondary" />
        {filename ? <Text style={[styles.sheetFileName, RTL_TEXT]}>{filename}</Text> : null}
        {error ? <Notice compact message={error} variant="danger" /> : null}
        <Button
          disabled={asset === null || saving}
          label={saving ? "در حال ذخیره…" : "ذخیره تصویر"}
          loading={saving}
          onPress={() => void submit()}
        />
      </View>
    </Sheet>
  );
}

function PriceOverrideSheet({
  api,
  food,
  onClose,
  onSaved,
}: {
  readonly api: NutritionCatalogueApi;
  readonly food: AdminFoodCatalogueItem | null;
  readonly onClose: () => void;
  readonly onSaved: () => void;
}) {
  const [price, setPrice] = useState(() => {
    const value = food === null ? null : priceInToman(food.price);
    return value === null ? "" : String(value);
  });
  const [unit, setUnit] = useState<FoodPriceOverrideInput["canonical_unit"]>(() => (
    food === null ? "TOMAN_PER_KG" : canonicalUnitForOverride(food.price.canonical_unit)
  ));
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [researching, setResearching] = useState(false);
  const [researchResult, setResearchResult] = useState<SingleFoodPriceResearchResponse | null>(null);
  const [researchError, setResearchError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runResearch(): Promise<void> {
    if (food === null) return;
    setResearching(true);
    setResearchError(null);
    try {
      const result = await api.researchFoodPrice(food.slug);
      setResearchResult(result);
      if (result.status === "success" && result.candidate_reference_price_toman) {
        setPrice(result.candidate_reference_price_toman);
        if (result.canonical_unit) setUnit(canonicalUnitForOverride(result.canonical_unit));
        setReason((current) => current || "استعلام خودکار از فروشگاه‌های آنلاین توسط ایجنت");
      } else if (result.status === "failed" || result.status === "no_quotes") {
        setResearchError(result.message ?? "قیمتی در فروشگاه‌ها یافت نشد.");
      }
    } catch (requestError) {
      setResearchError(mobileRequestErrorMessage(requestError, "خطا در برقراری ارتباط با سرویس استعلام قیمت."));
    } finally {
      setResearching(false);
    }
  }

  async function submit(): Promise<void> {
    const numericPrice = Number(price);
    if (!Number.isFinite(numericPrice) || numericPrice <= 0 || reason.trim().length < 5 || food === null) {
      setError("قیمت و دلیل ویرایش را معتبر وارد کن.");
      return;
    }
    setError(null);
    setSaving(true);
    try {
      await api.saveFoodPriceOverride(food.slug, {
        canonical_unit: unit,
        reason: reason.trim(),
        reference_price_toman: price.trim(),
      });
      onSaved();
    } catch (requestError) {
      setError(mobileRequestErrorMessage(requestError, "قیمت ذخیره نشد."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet onClose={onClose} title="ویرایش قیمت" visible={food !== null}>
      <View style={styles.sheetStack}>
        <Text style={[styles.sheetTitle, RTL_TEXT]}>قیمت و استعلام هوشمند</Text>
        <Text style={[styles.sheetHelper, RTL_TEXT]}>این قیمت با اجرای موفق بعدی بازار منقضی می‌شود.</Text>
        <Button
          disabled={researching || saving}
          label={researching ? "در حال جستجوی آنلاین قیمت… (ممکن است ۱ تا ۲ دقیقه طول بکشد)" : "⚡ استعلام هوشمند قیمت با ایجنت"}
          onPress={() => void runResearch()}
          variant="secondary"
        />
        {researchError ? <Notice compact message={researchError} variant="danger" /> : null}
        {researchResult?.quotes && researchResult.quotes.length > 0 ? (
          <View style={styles.quoteStack}>
            <Text style={[styles.sheetLabel, RTL_TEXT]}>قیمت‌های کشف‌شده در فروشگاه‌ها:</Text>
            {researchResult.quotes.map((quote, index) => (
              <View key={`${quote.source_url}-${index}`} style={styles.quoteRow}>
                <Text style={[styles.quoteText, RTL_TEXT]}>
                  {quote.source_name} ({quote.source_domain}): {formatCatalogueDisplayNumber(quote.normal_price_toman, 0)} تومان ({formatCatalogueDisplayNumber(quote.package_quantity, 1)} {quote.package_unit})
                </Text>
                <Button
                  label="مشاهده منبع"
                  onPress={() => void Linking.openURL(quote.source_url).catch(() => undefined)}
                  variant="ghost"
                />
              </View>
            ))}
            {researchResult.candidate_reference_price_toman ? (
              <Text style={[styles.suggestedPrice, RTL_TEXT]}>
                قیمت پیشنهادی بازار: {formatCatalogueDisplayNumber(researchResult.candidate_reference_price_toman, 0)} تومان
              </Text>
            ) : null}
          </View>
        ) : null}
        <TextField
          accessibilityLabel="قیمت"
          keyboardType="decimal-pad"
          label="قیمت (تومان)"
          onChangeText={setPrice}
          required
          textDirection="ltr"
          value={price}
        />
        <Text style={[styles.sheetLabel, RTL_TEXT]}>واحد</Text>
        <View style={[styles.basisChoices, RTL_ROW]}>
          <BasisChoice label="تومان/کیلوگرم" onPress={() => setUnit("TOMAN_PER_KG")} selected={unit === "TOMAN_PER_KG"} />
          <BasisChoice label="تومان/لیتر" onPress={() => setUnit("TOMAN_PER_LITER")} selected={unit === "TOMAN_PER_LITER"} />
          <BasisChoice label="تومان/عدد" onPress={() => setUnit("TOMAN_PER_UNIT")} selected={unit === "TOMAN_PER_UNIT"} />
        </View>
        <TextField
          accessibilityLabel="دلیل"
          label="دلیل ویرایش"
          multiline
          onChangeText={setReason}
          required
          value={reason}
        />
        {error ? <Notice compact message={error} variant="danger" /> : null}
        <Button
          disabled={saving || researching}
          label={saving ? "در حال ذخیره…" : "ذخیره قیمت"}
          loading={saving}
          onPress={() => void submit()}
        />
      </View>
    </Sheet>
  );
}

function canonicalUnitForOverride(value: string | null | undefined): FoodPriceOverrideInput["canonical_unit"] {
  if (value === "TOMAN_PER_LITER" || value === "IRR_PER_LITER") return "TOMAN_PER_LITER";
  if (value === "TOMAN_PER_UNIT" || value === "IRR_PER_UNIT") return "TOMAN_PER_UNIT";
  return "TOMAN_PER_KG";
}

function DeleteFoodSheet({
  food,
  onClose,
  onDelete,
}: {
  readonly food: AdminFoodCatalogueItem | null;
  readonly onClose: () => void;
  readonly onDelete: (food: AdminFoodCatalogueItem) => Promise<void>;
}) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirmDelete(): Promise<void> {
    if (food === null) return;
    setDeleting(true);
    setError(null);
    try {
      await onDelete(food);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "حذف ماده غذایی انجام نشد.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <Sheet onClose={onClose} title="حذف ماده غذایی؟" visible={food !== null}>
      <View style={styles.sheetStack}>
        {food ? <Text style={[styles.sheetText, RTL_TEXT]}>«{food.name_fa}» از کاتالوگ فعال حذف شود؟</Text> : null}
        <Text style={[styles.deleteWarning, RTL_TEXT]}>این ماده دیگر در کاتالوگ و برنامه‌های غذایی جدید استفاده نمی‌شود، اما اطلاعات و سوابق تاریخی آن حذف نخواهند شد.</Text>
        {error ? <Notice compact message={error} variant="danger" /> : null}
        <View style={[styles.sheetActions, RTL_ROW]}>
          <Button disabled={deleting} label="انصراف" onPress={onClose} variant="ghost" />
          <Button
            disabled={deleting}
            label={deleting ? "در حال حذف…" : "حذف ماده غذایی"}
            loading={deleting}
            onPress={() => void confirmDelete()}
            variant="danger"
          />
        </View>
      </View>
    </Sheet>
  );
}

function BasisChoice({ label, onPress, selected }: { readonly label: string; readonly onPress: () => void; readonly selected: boolean }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={[styles.basisChoice, selected && styles.basisChoiceSelected]}
    >
      <Text style={[styles.basisChoiceText, selected && styles.basisChoiceTextSelected, RTL_TEXT]}>{label}</Text>
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
  cardStack: {
    gap: fiticianTokens.spacing[3],
  },
  foodActionAmber: {
    backgroundColor: "rgba(255,215,152,0.12)",
    borderColor: "#ffd798",
  },
  foodActionAmberText: {
    color: "#ffd798",
  },
  foodActionButton: {
    alignItems: "center",
    backgroundColor: "rgba(50,216,204,0.08)",
    borderColor: "rgba(50,216,204,0.55)",
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    justifyContent: "center",
    minHeight: 38,
    paddingHorizontal: 12,
    paddingVertical: 7,
  },
  foodActionDanger: {
    backgroundColor: "rgba(248,113,113,0.10)",
    borderColor: "rgba(248,113,113,0.68)",
  },
  foodActionDangerText: {
    color: "#fca5a5",
  },
  foodActionDisabled: {
    opacity: 0.46,
  },
  foodActionText: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 19,
  },
  foodActions: {
    alignItems: "center",
    direction: "rtl",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
    justifyContent: "flex-start",
  },
  foodAddButton: {
    alignItems: "center",
    backgroundColor: "#ffd798",
    borderColor: "#ffd798",
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    justifyContent: "center",
    minHeight: 46,
    paddingHorizontal: fiticianTokens.spacing[4],
    paddingVertical: fiticianTokens.spacing[3],
    width: "100%",
  },
  foodAddButtonText: {
    color: "#13201c",
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 24,
  },
  foodBackButton: {
    alignItems: "center",
    borderColor: "rgba(50,216,204,0.55)",
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    justifyContent: "center",
    minHeight: 40,
    paddingHorizontal: 16,
  },
  foodBackButtonText: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 21,
  },
  foodBasis: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
  },
  foodCard: {
    backgroundColor: "#0a1b1a",
    borderColor: "rgba(50,216,204,0.32)",
    borderRadius: 20,
    borderWidth: 1,
    elevation: 3,
    gap: fiticianTokens.spacing[3],
    overflow: "hidden",
    padding: 14,
    shadowColor: "#000000",
    shadowOffset: { height: 2, width: 0 },
    shadowOpacity: 0.18,
    shadowRadius: 8,
    width: "100%",
  },
  foodCardCategory: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 19,
  },
  foodCardCopy: {
    direction: "rtl",
    flex: 1,
    gap: fiticianTokens.spacing[2],
    minWidth: 0,
  },
  foodCardEnglish: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 18,
    textAlign: "left",
    writingDirection: "ltr",
  },
  foodCardIdentity: {
    alignItems: "flex-start",
    direction: "ltr",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    minWidth: 0,
    width: "100%",
  },
  foodCardNames: {
    alignItems: "stretch",
    direction: "rtl",
    flex: 1,
    gap: 2,
    minWidth: 0,
  },
  foodThumbnail: {
    borderColor: "rgba(50,216,204,0.34)",
    borderWidth: 1,
    flexShrink: 0,
    height: 96,
    width: 96,
  },
  foodCardTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.lg,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 27,
  },
  foodCardTitleRow: {
    alignItems: "flex-start",
    direction: "ltr",
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
    justifyContent: "space-between",
    minWidth: 0,
  },
  foodCatalogueStack: {
    gap: fiticianTokens.spacing[3],
  },
  foodCalories: {
    alignItems: "flex-end",
    flexShrink: 0,
    gap: 1,
  },
  foodCaloriesLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 18,
  },
  foodCaloriesValue: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 21,
    writingDirection: "ltr",
  },
  foodChip: {
    alignItems: "center",
    backgroundColor: "rgba(10,31,30,0.72)",
    borderColor: "rgba(234,244,241,0.16)",
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    justifyContent: "center",
    minHeight: 40,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  foodChipRow: {
    alignItems: "center",
    gap: fiticianTokens.spacing[2],
    paddingVertical: 1,
  },
  foodChipScroller: {
    width: "100%",
  },
  foodChipSelected: {
    backgroundColor: "#32d8cc",
    borderColor: "#32d8cc",
  },
  foodChipText: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 19,
  },
  foodChipTextSelected: {
    color: "#09201d",
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
  },
  foodHero: {
    alignItems: "center",
    justifyContent: "space-between",
    minHeight: 48,
    width: "100%",
  },
  foodHeroTitle: {
    color: fiticianTokens.colors.ink,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h1,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 40,
  },
  foodMacroCell: {
    alignItems: "center",
    flex: 1,
    gap: 1,
    justifyContent: "center",
    minWidth: 0,
    paddingHorizontal: 5,
  },
  foodMacroCellDivider: {
    borderLeftColor: "rgba(234,244,241,0.14)",
    borderLeftWidth: 1,
  },
  foodMacroLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 18,
    textAlign: "center",
  },
  foodMacroStrip: {
    borderBottomColor: "rgba(234,244,241,0.14)",
    borderBottomWidth: 1,
    borderTopColor: "rgba(234,244,241,0.14)",
    borderTopWidth: 1,
    flexDirection: "row",
    minHeight: 58,
    width: "100%",
  },
  foodMacroValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 21,
    writingDirection: "ltr",
  },
  foodPagination: {
    alignItems: "center",
    justifyContent: "space-between",
    width: "100%",
  },
  foodPaginationText: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 21,
  },
  foodPriceError: {
    color: "#991b1b",
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 18,
  },
  foodPriceMeta: {
    color: "#624b28",
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 18,
  },
  foodPriceMissing: {
    backgroundColor: "rgba(234,244,241,0.06)",
    borderColor: "rgba(234,244,241,0.16)",
  },
  foodPriceTicket: {
    backgroundColor: "#ffd798",
    borderColor: "rgba(255,215,152,0.80)",
    borderRadius: 14,
    borderWidth: 1,
    direction: "rtl",
    gap: 2,
    paddingHorizontal: 12,
    paddingVertical: 9,
    width: "100%",
  },
  foodPriceTicketError: {
    backgroundColor: "rgba(255,107,107,0.08)",
    borderColor: "rgba(255,107,107,0.38)",
  },
  foodPriceTicketResearching: {
    backgroundColor: "rgba(255,215,152,0.09)",
    borderColor: "rgba(255,215,152,0.35)",
  },
  foodPriceTitle: {
    color: "#624b28",
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 18,
    textAlign: "right",
    writingDirection: "rtl",
  },
  foodPriceUnit: {
    color: "#624b28",
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 18,
    textAlign: "right",
    writingDirection: "rtl",
  },
  foodPriceValue: {
    color: "#13201c",
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 24,
    textAlign: "right",
    writingDirection: "rtl",
  },
  foodSearchButton: {
    alignItems: "center",
    backgroundColor: "#32d8cc",
    borderBottomLeftRadius: 12,
    borderBottomRightRadius: 0,
    borderTopLeftRadius: 12,
    borderTopRightRadius: 0,
    justifyContent: "center",
    minHeight: 48,
    paddingHorizontal: 16,
  },
  foodSearchButtonText: {
    color: "#09201d",
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 21,
  },
  foodSearchInput: {
    backgroundColor: "#061513",
    borderBottomLeftRadius: 0,
    borderBottomRightRadius: 12,
    borderColor: "rgba(234,244,241,0.16)",
    borderTopLeftRadius: 0,
    borderTopRightRadius: 12,
    borderWidth: 1,
    color: fiticianTokens.colors.ink,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    minHeight: 48,
    minWidth: 0,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  foodSearchRow: {
    alignItems: "stretch",
    flexDirection: "row",
    width: "100%",
  },
  foodToolbar: {
    backgroundColor: "rgba(4,17,16,0.92)",
    borderColor: "rgba(234,244,241,0.12)",
    borderRadius: 18,
    borderWidth: 1,
    gap: fiticianTokens.spacing[3],
    padding: 12,
    width: "100%",
  },
  quoteRow: {
    backgroundColor: "rgba(10,31,30,0.70)",
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    gap: fiticianTokens.spacing[2],
    padding: fiticianTokens.spacing[3],
  },
  quoteStack: {
    gap: fiticianTokens.spacing[2],
  },
  quoteText: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
  },
  basisChoice: {
    alignItems: "center",
    backgroundColor: "rgba(10,31,30,0.70)",
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    justifyContent: "center",
    minHeight: 42,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  basisChoiceSelected: {
    backgroundColor: "rgba(50,216,204,0.18)",
    borderColor: fiticianTokens.colors.aqua,
  },
  basisChoiceText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 19,
  },
  basisChoiceTextSelected: {
    color: fiticianTokens.colors.aqua,
  },
  basisChoices: {
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  detailStack: {
    gap: fiticianTokens.spacing[2],
  },
  deleteWarning: {
    backgroundColor: "rgba(248,113,113,0.10)",
    borderColor: "rgba(248,113,113,0.36)",
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    color: "#fecaca",
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    padding: fiticianTokens.spacing[3],
  },
  section: {
    gap: fiticianTokens.spacing[3],
    marginTop: fiticianTokens.spacing[5],
  },
  sheetStack: {
    gap: fiticianTokens.spacing[3],
  },
  sheetActions: {
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
    justifyContent: "flex-start",
  },
  sheetFileName: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 22,
  },
  sheetHelper: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
  },
  sheetLabel: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    lineHeight: 22,
  },
  sheetText: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    lineHeight: 26,
  },
  sheetTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  suggestedPrice: {
    backgroundColor: "rgba(50,216,204,0.10)",
    borderColor: "rgba(50,216,204,0.28)",
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    padding: fiticianTokens.spacing[3],
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
