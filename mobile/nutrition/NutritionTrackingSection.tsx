import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as ImagePicker from "expo-image-picker";
import { File } from "expo-file-system";
import { useEffect, useMemo, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import type { components, MultipartUploadRequest } from "@fitician/core";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { nutritionKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import { useAndroidBackHandler } from "../ui/navigation/BackBehaviorProvider";
import { Button, Card, Dialog, EmptyState, Notice, PageHeading, Skeleton, TextField } from "../ui/components";
import { getMobileViewState, mobileRequestErrorMessage } from "../ui/requestState";
import { fiticianTokens } from "../ui/tokens";
import { UploadCancellationError, UploadManager, type UploadHandle } from "../upload/uploadManager";
import {
  createFoodPhotoUploadJob,
  FOOD_PHOTO_PICKER_OPTIONS,
  nutritionMimeTypeForAsset,
} from "./nutritionUpload";
import {
  createNutritionCatalogueApi,
  type FoodCatalogueItem,
} from "./nutritionCatalogueApi";
import {
  adherencePercentLabel,
  checkInStatusLabel,
  photoEstimatePresentation,
  trackingDataStatusLabel,
  trackingSourceLabel,
} from "./nutritionTrackingModel";
import {
  createNutritionTrackingApi,
  type NutritionFoodPhotoEstimate,
} from "./nutritionTrackingApi";
import { createNutritionApi, type NutritionEstimate } from "./nutritionApi";
import { formatNutritionNumber } from "./nutritionModel";

type CheckInStatus = components["schemas"]["NutritionDailyCheckInStatus"];
type TrackingEntry = components["schemas"]["NutritionTrackingEntryResponse"];
type EntrySource = components["schemas"]["NutritionConsumptionSource"];
type PhotoItem = components["schemas"]["NutritionFoodPhotoItemResponse"];

const checkInOptions: readonly CheckInStatus[] = [
  "on_plan",
  "mostly_on_plan",
  "off_plan",
  "not_recorded",
];

const entrySourceOptions: readonly (EntrySource | "all")[] = [
  "all",
  "catalogue_manual",
  "quick_approximation",
  "photo_estimated_confirmed",
  "planned_confirmed",
  "planned_adjusted",
];

export function NutritionTrackingSection() {
  const auth = useMobileAuth();
  const queryClient = useQueryClient();
  const connectivityStatus = useConnectivityStatus();
  const entryDate = useMemo(todayIsoDate, []);
  const api = useMemo(
    () => createNutritionTrackingApi(auth.request, auth.download),
    [auth.download, auth.request],
  );
  const nutritionApi = useMemo(() => createNutritionApi(auth.request), [auth.request]);
  const catalogueApi = useMemo(() => createNutritionCatalogueApi(auth.request), [auth.request]);
  const dailyQuery = useQuery({
    queryFn: () => api.getDailyTracking(entryDate),
    queryKey: nutritionKeys.tracking(entryDate),
  });
  const recentQuery = useQuery({
    queryFn: () => api.getRecentFoods(20),
    queryKey: nutritionKeys.recentFoods(),
  });
  const catalogueQuery = useQuery({
    queryFn: () => catalogueApi.getFoodCatalogue({ page: 1, pageSize: 40 }),
    queryKey: nutritionKeys.foodCatalogue({ category: "", page: 1, pageSize: 40, query: "" }),
  });
  const estimateQuery = useQuery({
    queryFn: nutritionApi.getCurrentEstimate,
    queryKey: nutritionKeys.estimate(),
  });
  const dailyState = getMobileViewState(dailyQuery, { connectivityStatus });
  const recentState = getMobileViewState(recentQuery, { connectivityStatus });
  const catalogueState = getMobileViewState(catalogueQuery, { connectivityStatus });
  const estimateState = getMobileViewState(estimateQuery, { connectivityStatus });
  const daily = stateData(dailyState);
  const recentFoods = stateData(recentState) ?? [];
  const catalogueFoods = stateData(catalogueState)?.items ?? [];
  const estimate = stateData(estimateState) ?? null;
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [checkInStatus, setCheckInStatus] = useState<CheckInStatus | null>(null);
  const [sourceFilter, setSourceFilter] = useState<EntrySource | "all">("all");
  const [selectedFoodId, setSelectedFoodId] = useState<string | null>(null);
  const [catalogueSearch, setCatalogueSearch] = useState("");
  const [catalogueGrams, setCatalogueGrams] = useState("100");
  const [quickName, setQuickName] = useState("وعده تقریبی");
  const [quickCalories, setQuickCalories] = useState("");
  const [quickProtein, setQuickProtein] = useState("");
  const [entryAmounts, setEntryAmounts] = useState<Record<string, string>>({});
  const [entryToDelete, setEntryToDelete] = useState<TrackingEntry | null>(null);
  const [photoConsent, setPhotoConsent] = useState(false);
  const [photoEstimate, setPhotoEstimate] = useState<NutritionFoodPhotoEstimate | null>(null);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [photoSuccess, setPhotoSuccess] = useState<string | null>(null);
  const [photoUploading, setPhotoUploading] = useState(false);
  const [photoActionBusy, setPhotoActionBusy] = useState(false);
  const [photoAmounts, setPhotoAmounts] = useState<Record<string, string>>({});
  const [photoFoodIds, setPhotoFoodIds] = useState<Record<string, string>>({});
  const photoUploadRef = useRef<UploadHandle<NutritionFoodPhotoEstimate> | null>(null);
  const uploadManager = useMemo(
    () => new UploadManager({
      executor: async <TResponse,>(request: MultipartUploadRequest) => auth.upload<TResponse>(request),
    }),
    [auth.upload],
  );

  useAndroidBackHandler(
    "upload",
    () => {
      const upload = photoUploadRef.current;
      if (upload === null || !photoUploading) return false;
      upload.cancel();
      return true;
    },
    photoUploading,
  );

  const filteredCatalogueFoods = catalogueFoods.filter((food) => {
    const normalizedSearch = catalogueSearch.trim().toLocaleLowerCase();
    return normalizedSearch.length === 0
      || food.name_fa.toLocaleLowerCase().includes(normalizedSearch)
      || food.name_en.toLocaleLowerCase().includes(normalizedSearch);
  });
  const selectedFood = catalogueFoods.find((food) => food.id === selectedFoodId) ?? null;
  const visibleEntries = daily?.entries.filter(
    (entry) => sourceFilter === "all" || entry.source === sourceFilter,
  ) ?? [];
  const checkInValue = checkInStatus ?? daily?.check_in_status ?? "not_recorded";

  useEffect(() => {
    if (selectedFoodId === null && catalogueFoods[0] !== undefined) {
      setSelectedFoodId(catalogueFoods[0].id);
    }
  }, [catalogueFoods, selectedFoodId]);

  async function refreshDaily(): Promise<void> {
    await queryClient.invalidateQueries({ queryKey: nutritionKeys.tracking(entryDate) });
    await queryClient.invalidateQueries({ queryKey: nutritionKeys.recentFoods() });
    await queryClient.invalidateQueries({ queryKey: ["nutrition", "adherence"] });
    await queryClient.invalidateQueries({ queryKey: ["nutrition", "tracking-history"] });
  }

  async function saveCheckIn(status: CheckInStatus): Promise<void> {
    setActionError(null);
    setActionBusy(true);
    try {
      const result = await api.saveDailyCheckIn({ entry_date: entryDate, status });
      queryClient.setQueryData(nutritionKeys.tracking(entryDate), result);
      queryClient.invalidateQueries({ queryKey: ["nutrition", "adherence"] });
      queryClient.invalidateQueries({ queryKey: ["nutrition", "tracking-history"] });
      setCheckInStatus(status);
    } catch (error) {
      setActionError(nutritionTrackingError(error));
    } finally {
      setActionBusy(false);
    }
  }

  async function addCatalogueFood(food: FoodCatalogueItem | null = selectedFood): Promise<void> {
    const grams = numericValue(catalogueGrams);
    if (food === null || !Number.isFinite(grams) || grams <= 0) {
      setActionError("یک ماده غذایی و مقدار معتبر انتخاب کن.");
      return;
    }
    setActionError(null);
    setActionBusy(true);
    try {
      await api.addCatalogueFood({ entry_date: entryDate, food_id: food.id, grams, note: null });
      setCatalogueGrams("100");
      await refreshDaily();
    } catch (error) {
      setActionError(nutritionTrackingError(error));
    } finally {
      setActionBusy(false);
    }
  }

  async function addRecentFood(foodId: string, grams: number | null): Promise<void> {
    setSelectedFoodId(foodId);
    setCatalogueGrams(String(grams ?? 100));
    const amount = grams ?? 100;
    setActionError(null);
    setActionBusy(true);
    try {
      await api.addCatalogueFood({ entry_date: entryDate, food_id: foodId, grams: amount, note: null });
      await refreshDaily();
    } catch (error) {
      setActionError(nutritionTrackingError(error));
    } finally {
      setActionBusy(false);
    }
  }

  async function addQuickApproximation(): Promise<void> {
    const calories = numericValue(quickCalories);
    const protein = quickProtein.trim().length === 0 ? null : numericValue(quickProtein);
    if (quickName.trim().length === 0 || !Number.isFinite(calories) || calories <= 0 || (protein !== null && (!Number.isFinite(protein) || protein < 0))) {
      setActionError("نام وعده و کالری معتبر وارد کن.");
      return;
    }
    setActionError(null);
    setActionBusy(true);
    try {
      await api.addQuickApproximation({
        calories,
        display_name: quickName.trim(),
        entry_date: entryDate,
        protein_g: protein,
      });
      setQuickCalories("");
      setQuickProtein("");
      await refreshDaily();
    } catch (error) {
      setActionError(nutritionTrackingError(error));
    } finally {
      setActionBusy(false);
    }
  }

  async function editEntry(entry: TrackingEntry): Promise<void> {
    const grams = numericValue(entryAmounts[entry.id] ?? String(entry.quantity_grams ?? ""));
    if (!Number.isFinite(grams) || grams <= 0) {
      setActionError("مقدار باید بیشتر از صفر باشد.");
      return;
    }
    setActionError(null);
    setActionBusy(true);
    try {
      await api.editEntry(entry.id, { grams });
      await refreshDaily();
    } catch (error) {
      setActionError(nutritionTrackingError(error));
    } finally {
      setActionBusy(false);
    }
  }

  async function removeEntry(): Promise<void> {
    if (entryToDelete === null) return;
    setActionError(null);
    setActionBusy(true);
    try {
      await api.removeEntry(entryToDelete.id);
      setEntryToDelete(null);
      await refreshDaily();
    } catch (error) {
      setActionError(nutritionTrackingError(error));
    } finally {
      setActionBusy(false);
    }
  }

  async function adjustPlannedMeal(entry: TrackingEntry, status: "adjusted" | "skipped"): Promise<void> {
    if (entry.planned_meal_id === null) return;
    setActionError(null);
    setActionBusy(true);
    try {
      const result = await api.adjustPlannedMeal(entry.planned_meal_id, {
        entry_date: entryDate,
        portion_ratio: status === "adjusted" ? 0.5 : null,
        status,
      });
      queryClient.setQueryData(nutritionKeys.tracking(entryDate), result);
      queryClient.invalidateQueries({ queryKey: ["nutrition", "adherence"] });
      queryClient.invalidateQueries({ queryKey: ["nutrition", "tracking-history"] });
    } catch (error) {
      setActionError(nutritionTrackingError(error));
    } finally {
      setActionBusy(false);
    }
  }

  async function choosePhoto(source: "camera" | "gallery"): Promise<void> {
    if (!photoConsent) {
      setPhotoError("برای تخمین عکس، رضایت پردازش عکس را فعال کن.");
      return;
    }
    setPhotoError(null);
    setPhotoSuccess(null);
    try {
      if (source === "camera") {
        const permission = await ImagePicker.requestCameraPermissionsAsync();
        if (!permission.granted) throw new Error("Camera permission denied");
      }
      const result = source === "camera"
        ? await ImagePicker.launchCameraAsync(FOOD_PHOTO_PICKER_OPTIONS)
        : await ImagePicker.launchImageLibraryAsync(FOOD_PHOTO_PICKER_OPTIONS);
      if (result.canceled) return;
      const selected = result.assets[0];
      if (selected === undefined) throw new Error("No food photo was selected");
      const mimeType = nutritionMimeTypeForAsset(selected.mimeType, selected.uri);
      if (mimeType === null) throw new Error("Unsupported food-photo format");
      const bytes = new Uint8Array(await new File(selected.uri).arrayBuffer());
      const orientation = selected.exif?.Orientation;
      const handle = uploadManager.enqueue<NutritionFoodPhotoEstimate>(createFoodPhotoUploadJob({
        asset: {
          bytes,
          filename: "meal-photo",
          height: selected.height,
          mimeType,
          orientation: typeof orientation === "number" ? orientation : null,
          width: selected.width,
        },
        consent: true,
        language: "fa",
      }));
      photoUploadRef.current = handle;
      setPhotoUploading(true);
      setPhotoEstimate(await handle.promise);
      setPhotoAmounts({});
      setPhotoFoodIds({});
    } catch (error) {
      if (!(error instanceof UploadCancellationError)) {
        setPhotoError(photoErrorMessage(error));
      }
    } finally {
      photoUploadRef.current = null;
      setPhotoUploading(false);
    }
  }

  async function correctPhotoItem(item: PhotoItem): Promise<void> {
    if (photoEstimate === null) return;
    const amount = numericValue(photoAmounts[item.item_id] ?? String(item.estimated_amount));
    const foodId = photoFoodIds[item.item_id];
    if (!Number.isFinite(amount) || amount <= 0) {
      setPhotoError("مقدار عکس باید بیشتر از صفر باشد.");
      return;
    }
    if (item.mapping_status === "unresolved" && foodId === undefined) {
      setPhotoError("برای مورد نامشخص، یک ماده غذایی انتخاب کن.");
      return;
    }
    setPhotoActionBusy(true);
    setPhotoError(null);
    try {
      setPhotoEstimate(await api.correctPhotoItem(photoEstimate.id, item.item_id, {
        estimated_amount: amount,
        food_id: foodId,
        remove: false,
      }));
    } catch (error) {
      setPhotoError(photoErrorMessage(error));
    } finally {
      setPhotoActionBusy(false);
    }
  }

  async function removePhotoItem(item: PhotoItem): Promise<void> {
    if (photoEstimate === null) return;
    setPhotoActionBusy(true);
    setPhotoError(null);
    try {
      setPhotoEstimate(await api.correctPhotoItem(photoEstimate.id, item.item_id, { remove: true }));
    } catch (error) {
      setPhotoError(photoErrorMessage(error));
    } finally {
      setPhotoActionBusy(false);
    }
  }

  async function confirmPhoto(): Promise<void> {
    if (photoEstimate === null) return;
    const presentation = photoEstimatePresentation(photoEstimate);
    if (!presentation.canConfirm || !photoEstimate.macro_totals_complete) return;
    setPhotoActionBusy(true);
    setPhotoError(null);
    try {
      await api.confirmPhoto(photoEstimate.id, { entry_date: entryDate });
      setPhotoEstimate(null);
      setPhotoSuccess("برآورد عکس پس از تأیید تو در ثبت امروز ذخیره شد.");
      await refreshDaily();
    } catch (error) {
      setPhotoError(photoErrorMessage(error));
    } finally {
      setPhotoActionBusy(false);
    }
  }

  async function clearPhotoEstimate(): Promise<void> {
    if (photoEstimate === null) return;
    setPhotoActionBusy(true);
    setPhotoError(null);
    try {
      await api.deletePhotoEstimate(photoEstimate.id);
      setPhotoEstimate(null);
      setPhotoSuccess("برآورد عکس پاک شد.");
    } catch (error) {
      setPhotoError(photoErrorMessage(error));
    } finally {
      setPhotoActionBusy(false);
    }
  }

  if (dailyState.status === "loading") return <Skeleton height={720} />;
  if (dailyState.status === "error" && daily === undefined) {
    return (
      <Notice
        actionLabel="تلاش دوباره"
        message="ثبت‌های تغذیه امروز دریافت نشد."
        onAction={() => void dailyQuery.refetch()}
        variant="danger"
      />
    );
  }
  if (dailyState.status === "offline" && daily === undefined) {
    return <Notice message="برای ثبت و مشاهده تغذیه امروز به اینترنت وصل شو." variant="offline" />;
  }
  if (daily === undefined) return null;

  return (
    <View style={styles.section}>
      <PageHeading
        eyebrow="امروز"
        supportingText="مقدارهای ثبت‌شده با دقت ذخیره‌شده سرور محاسبه می‌شوند؛ اینجا فقط نمایش گرد شده است."
        title="ثبت تغذیه"
      />
      {dailyState.status === "offline" || dailyState.status === "stale" ? (
        <Notice message="آخرین ثبت ذخیره‌شده نمایش داده می‌شود؛ تغییرات جدید بعد از اتصال انجام می‌شوند." variant="offline" />
      ) : null}
      {estimateState.status === "offline" || estimateState.status === "stale" || estimate?.is_stale ? (
        <Notice compact message="هدف‌های ذخیره‌شده نمایش داده می‌شوند؛ ممکن است با آخرین وضعیت پروفایل هماهنگ نباشند." variant="offline" />
      ) : null}
      {estimateState.status === "error" && estimate === null ? (
        <Notice compact message="هدف برنامه دریافت نشد؛ ثبت‌های واقعی امروز همچنان در دسترس هستند." variant="warning" />
      ) : null}
      <Card style={styles.summaryCard}>
        <View style={styles.summaryHeading}>
          <Text style={styles.cardTitle}>مصرف واقعی امروز</Text>
          <Text style={styles.dateText}>{entryDate}</Text>
        </View>
        <View style={styles.metricRow}>
          <Metric
            label="انرژی"
            target={nutritionTargetLabel(estimate, ["goal_calories", "energy"], "کیلوکالری")}
            value={displayNutrient(daily.actual_totals.energy_kcal ?? daily.actual_totals.calories)}
            unit="kcal"
          />
          <Metric
            label="پروتئین"
            target={nutritionTargetLabel(estimate, ["protein", "protein_g"], "گرم")}
            value={displayNutrient(daily.actual_totals.protein_g)}
            unit="g"
          />
          <Metric label="ثبت‌ها" value={formatNutritionNumber(daily.entries.length)} unit="" />
        </View>
        <View style={styles.dataStatusRow}>
          <Text style={styles.mutedText}>کیفیت داده</Text>
          <Text style={styles.statusText}>{trackingDataStatusLabel(daily.data_status)}</Text>
        </View>
      </Card>

      <FoodPhotoCard
        actionBusy={photoActionBusy}
        catalogueFoods={catalogueFoods}
        consent={photoConsent}
        error={photoError}
        estimate={photoEstimate}
        foodIds={photoFoodIds}
        amounts={photoAmounts}
        onAmountChange={(itemId, amount) => setPhotoAmounts((current) => ({ ...current, [itemId]: amount }))}
        onChooseFood={(itemId, foodId) => setPhotoFoodIds((current) => ({ ...current, [itemId]: foodId }))}
        onConfirm={() => void confirmPhoto()}
        onConsentChange={setPhotoConsent}
        onDeleteItem={(item) => void removePhotoItem(item)}
        onPickCamera={() => void choosePhoto("camera")}
        onPickGallery={() => void choosePhoto("gallery")}
        onClear={() => void clearPhotoEstimate()}
        onCorrectItem={(item) => void correctPhotoItem(item)}
        uploading={photoUploading}
      />

      <Card style={styles.card}>
        <Text style={styles.cardTitle}>ثبت وضعیت امروز</Text>
        <Text style={styles.bodyText}>وضعیت روزت را ثبت کن تا شاخص پایبندی با داده واقعی محاسبه شود.</Text>
        <View style={styles.choiceRow}>
          {checkInOptions.map((status) => (
            <Pressable
              accessibilityLabel={checkInStatusLabel(status)}
              accessibilityRole="button"
              accessibilityState={{ disabled: actionBusy, selected: checkInValue === status }}
              disabled={actionBusy}
              key={status}
              onPress={() => void saveCheckIn(status)}
              style={[styles.choice, checkInValue === status && styles.choiceSelected]}
            >
              <Text style={[styles.choiceText, checkInValue === status && styles.choiceTextSelected]}>{checkInStatusLabel(status)}</Text>
            </Pressable>
          ))}
        </View>
      </Card>

      {actionError !== null ? <Notice message={actionError} variant="danger" /> : null}
      {photoSuccess !== null ? <Notice message={photoSuccess} variant="success" /> : null}

      <Card style={styles.card}>
        <View style={styles.sectionHeading}>
          <View style={styles.headingCopy}>
            <Text style={styles.cardTitle}>ثبت دستی وعده</Text>
            <Text style={styles.bodyText}>غذای دقیق را از کاتالوگ انتخاب کن یا یک برآورد سریع وارد کن.</Text>
          </View>
        </View>
        <TextField
          accessibilityLabel="جستجوی ماده غذایی برای ثبت"
          label="ماده غذایی"
          onChangeText={setCatalogueSearch}
          placeholder="جستجوی نام فارسی یا انگلیسی"
          value={catalogueSearch}
        />
        {catalogueState.status === "offline" || catalogueState.status === "stale" ? (
          <Notice message="فهرست مواد غذایی تازه‌سازی نشده است." variant="offline" />
        ) : null}
        {catalogueState.status === "error" ? (
          <Notice actionLabel="تلاش دوباره" message="فهرست مواد غذایی دریافت نشد." onAction={() => void catalogueQuery.refetch()} variant="danger" />
        ) : null}
        <View style={styles.foodChoiceRow}>
          {filteredCatalogueFoods.slice(0, 12).map((food) => (
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ selected: selectedFoodId === food.id }}
              key={food.id}
              onPress={() => setSelectedFoodId(food.id)}
              style={[styles.foodChoice, selectedFoodId === food.id && styles.foodChoiceSelected]}
            >
              <Text style={[styles.foodChoiceText, selectedFoodId === food.id && styles.choiceTextSelected]}>{food.name_fa}</Text>
            </Pressable>
          ))}
        </View>
        <View style={styles.inlineFields}>
          <TextField
            accessibilityLabel="مقدار به گرم"
            keyboardType="decimal-pad"
            label="مقدار به گرم"
            onChangeText={setCatalogueGrams}
            textDirection="ltr"
            value={catalogueGrams}
          />
          <Button disabled={actionBusy || selectedFood === null} label="ثبت از کاتالوگ" onPress={() => void addCatalogueFood()} />
        </View>
        <View style={styles.divider} />
        <TextField accessibilityLabel="نام وعده تقریبی" label="نام برآورد سریع" onChangeText={setQuickName} value={quickName} />
        <View style={styles.inlineFields}>
          <TextField
            accessibilityLabel="کالری تقریبی"
            keyboardType="decimal-pad"
            label="کالری تقریبی"
            onChangeText={setQuickCalories}
            textDirection="ltr"
            value={quickCalories}
          />
          <TextField
            accessibilityLabel="پروتئین تقریبی"
            keyboardType="decimal-pad"
            label="پروتئین تقریبی"
            onChangeText={setQuickProtein}
            textDirection="ltr"
            value={quickProtein}
          />
        </View>
        <Button disabled={actionBusy} label="ثبت برآورد سریع" onPress={() => void addQuickApproximation()} variant="secondary" />
      </Card>

      {recentFoods.length > 0 ? (
        <Card style={styles.card}>
          <Text style={styles.cardTitle}>غذاهای اخیر</Text>
          {recentState.status === "offline" || recentState.status === "stale" ? (
            <Notice message="غذاهای اخیر از آخرین نسخه ذخیره‌شده نمایش داده می‌شوند." variant="offline" />
          ) : null}
          <View style={styles.recentRow}>
            {recentFoods.slice(0, 8).map((food) => (
              <Button
                disabled={actionBusy}
                key={food.food_id}
                label={`${food.display_name} · ${displayNutrient(food.last_quantity_grams ?? 100)} g`}
                onPress={() => void addRecentFood(food.food_id, food.last_quantity_grams)}
                variant="ghost"
              />
            ))}
          </View>
        </Card>
      ) : null}

      <Card style={styles.card}>
        <View style={styles.sectionHeading}>
          <Text style={styles.cardTitle}>ثبت‌های امروز</Text>
          <Text style={styles.mutedText}>{formatNutritionNumber(visibleEntries.length)} مورد</Text>
        </View>
        <View style={styles.choiceRow}>
          {entrySourceOptions.map((source) => (
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ selected: sourceFilter === source }}
              key={source}
              onPress={() => setSourceFilter(source)}
              style={[styles.choice, sourceFilter === source && styles.choiceSelected]}
            >
              <Text style={[styles.choiceText, sourceFilter === source && styles.choiceTextSelected]}>{source === "all" ? "همه" : trackingSourceLabel(source)}</Text>
            </Pressable>
          ))}
        </View>
        {visibleEntries.length === 0 ? (
          <EmptyState title="هنوز ثبتی برای این فیلتر نیست">ثبت دقیق، سریع یا از روی برنامه را از همین صفحه شروع کن.</EmptyState>
        ) : (
          <View style={styles.entryStack}>
            {visibleEntries.map((entry) => (
              <TrackingEntryCard
                actionBusy={actionBusy}
                amount={entryAmounts[entry.id] ?? String(entry.quantity_grams ?? "")}
                entry={entry}
                key={entry.id}
                onAmountChange={(amount) => setEntryAmounts((current) => ({ ...current, [entry.id]: amount }))}
                onDelete={() => setEntryToDelete(entry)}
                onEdit={() => void editEntry(entry)}
                onPlannedChange={(status) => void adjustPlannedMeal(entry, status)}
              />
            ))}
          </View>
        )}
      </Card>
      <Dialog
        cancelLabel="انصراف"
        confirmLabel="حذف ثبت"
        destructive
        message={entryToDelete === null ? "" : `ثبت «${entryToDelete.display_name}» حذف شود؟`}
        onCancel={() => setEntryToDelete(null)}
        onClose={() => setEntryToDelete(null)}
        onConfirm={() => void removeEntry()}
        title="حذف ثبت تغذیه"
        visible={entryToDelete !== null}
      />
    </View>
  );
}

function FoodPhotoCard({
  actionBusy,
  amounts,
  catalogueFoods,
  consent,
  error,
  estimate,
  foodIds,
  onAmountChange,
  onChooseFood,
  onClear,
  onConfirm,
  onConsentChange,
  onDeleteItem,
  onPickCamera,
  onPickGallery,
  onCorrectItem,
  uploading,
}: {
  readonly actionBusy: boolean;
  readonly amounts: Readonly<Record<string, string>>;
  readonly catalogueFoods: readonly FoodCatalogueItem[];
  readonly consent: boolean;
  readonly error: string | null;
  readonly estimate: NutritionFoodPhotoEstimate | null;
  readonly foodIds: Readonly<Record<string, string>>;
  readonly onAmountChange: (itemId: string, value: string) => void;
  readonly onChooseFood: (itemId: string, foodId: string) => void;
  readonly onClear: () => void;
  readonly onConfirm: () => void;
  readonly onConsentChange: (value: boolean) => void;
  readonly onDeleteItem: (item: PhotoItem) => void;
  readonly onPickCamera: () => void;
  readonly onPickGallery: () => void;
  readonly onCorrectItem: (item: PhotoItem) => void;
  readonly uploading: boolean;
}) {
  const presentation = estimate === null ? null : photoEstimatePresentation(estimate);
  return (
    <Card style={styles.card}>
      <View style={styles.sectionHeading}>
        <View style={styles.headingCopy}>
          <Text style={styles.cardTitle}>عکس وعده</Text>
          <Text style={styles.bodyText}>تخمین از روی عکس غذا انجام می‌شود و تا تأیید تو ثبت نهایی نیست.</Text>
        </View>
      </View>
      <Pressable
        accessibilityRole="checkbox"
        accessibilityState={{ checked: consent }}
        onPress={() => onConsentChange(!consent)}
        style={styles.consentRow}
      >
        <View style={[styles.checkbox, consent && styles.checkboxChecked]}>
          {consent ? <Text style={styles.checkboxMark}>✓</Text> : null}
        </View>
        <Text style={styles.bodyText}>با پردازش عکس توسط سرویس ثالث موافقم.</Text>
      </Pressable>
      <View style={styles.photoActions}>
        <Button disabled={uploading || !consent} label="انتخاب از گالری" onPress={onPickGallery} variant="secondary" />
        <Button disabled={uploading || !consent} label="گرفتن عکس" onPress={onPickCamera} />
      </View>
      {uploading ? <Notice message="در حال بارگذاری و تحلیل عکس…" variant="info" /> : null}
      {error !== null ? <Notice message={error} variant="danger" /> : null}
      {estimate !== null && presentation !== null ? (
        <View style={styles.photoResult}>
          <Notice message={presentation.message} title={presentation.title} variant="warning" />
          <View style={styles.metricRow}>
            <Metric label="انرژی تخمینی" value={displayNutrient(estimate.macro_totals.energy_kcal ?? estimate.macro_totals.calories)} unit="kcal" />
            <Metric label="پروتئین" value={displayNutrient(estimate.macro_totals.protein_g)} unit="g" />
            <Metric label="چربی" value={displayNutrient(estimate.macro_totals.fat_g)} unit="g" />
          </View>
          {!estimate.macro_totals_complete ? (
            <Notice message="برای تکمیل نتیجه، موارد نامشخص را اصلاح یا حذف کن." variant="warning" />
          ) : null}
          <View style={styles.photoItems}>
            {estimate.items.map((item) => (
              <View key={item.item_id} style={styles.photoItem}>
                <View style={styles.sectionHeading}>
                  <Text style={styles.entryTitle}>{item.name_guess}</Text>
                  <Text style={styles.mutedText}>{item.mapping_status === "resolved" ? "تطبیق‌یافته" : "نیازمند بررسی"}</Text>
                </View>
                <Text style={styles.bodyText}>اعتماد: {adherencePercentLabel(item.confidence)} · واحد: {item.unit}</Text>
                {item.mapping_status === "unresolved" ? (
                  <View style={styles.foodChoiceRow}>
                    {catalogueFoods.slice(0, 8).map((food) => (
                      <Pressable
                        accessibilityRole="button"
                        accessibilityState={{ selected: foodIds[item.item_id] === food.id }}
                        key={food.id}
                        onPress={() => onChooseFood(item.item_id, food.id)}
                        style={[styles.foodChoice, foodIds[item.item_id] === food.id && styles.foodChoiceSelected]}
                      >
                        <Text style={styles.foodChoiceText}>{food.name_fa}</Text>
                      </Pressable>
                    ))}
                  </View>
                ) : null}
                <TextField
                  accessibilityLabel={`مقدار ${item.name_guess}`}
                  keyboardType="decimal-pad"
                  label="مقدار"
                  onChangeText={(value) => onAmountChange(item.item_id, value)}
                  textDirection="ltr"
                  value={amounts[item.item_id] ?? String(item.estimated_amount)}
                />
                <View style={styles.photoItemActions}>
                  <Button disabled={actionBusy} label="اعمال اصلاح" onPress={() => onCorrectItem(item)} variant="secondary" />
                  <Button disabled={actionBusy} label="حذف مورد" onPress={() => onDeleteItem(item)} variant="danger" />
                </View>
              </View>
            ))}
          </View>
          <Button
            disabled={actionBusy || !presentation.canConfirm || !estimate.macro_totals_complete}
            label="تأیید و ثبت در امروز"
            onPress={onConfirm}
          />
          <Button disabled={actionBusy} label="پاک کردن نتیجه" onPress={onClear} variant="ghost" />
        </View>
      ) : null}
    </Card>
  );
}

function TrackingEntryCard({
  actionBusy,
  amount,
  entry,
  onAmountChange,
  onDelete,
  onEdit,
  onPlannedChange,
}: {
  readonly actionBusy: boolean;
  readonly amount: string;
  readonly entry: TrackingEntry;
  readonly onAmountChange: (value: string) => void;
  readonly onDelete: () => void;
  readonly onEdit: () => void;
  readonly onPlannedChange: (status: "adjusted" | "skipped") => void;
}) {
  return (
    <View style={styles.entryCard}>
      <View style={styles.sectionHeading}>
        <View style={styles.headingCopy}>
          <Text style={styles.entryTitle}>{entry.display_name}</Text>
          <Text style={styles.mutedText}>{trackingSourceLabel(entry.source)}</Text>
        </View>
        <Text style={styles.statusText}>{entry.user_confirmed ? "تأییدشده" : "تخمینی"}</Text>
      </View>
      <View style={styles.entryMeta}>
        {entry.quantity_grams !== null ? <Text style={styles.bodyText}>{displayNutrient(entry.quantity_grams)} گرم</Text> : null}
        <Text style={styles.bodyText}>{displayNutrient(entry.nutrients.energy_kcal ?? entry.nutrients.calories)} kcal</Text>
        <Text style={styles.bodyText}>{displayNutrient(entry.nutrients.protein_g)} g پروتئین</Text>
      </View>
      {entry.quantity_grams !== null && entry.planned_meal_id === null ? (
        <View style={styles.inlineFields}>
          <TextField
            accessibilityLabel={`ویرایش مقدار ${entry.display_name}`}
            keyboardType="decimal-pad"
            label="ویرایش مقدار به گرم"
            onChangeText={onAmountChange}
            textDirection="ltr"
            value={amount}
          />
          <Button disabled={actionBusy} label="ذخیره مقدار" onPress={onEdit} variant="secondary" />
        </View>
      ) : null}
      {entry.planned_meal_id !== null ? (
        <View style={styles.photoItemActions}>
          <Button disabled={actionBusy} label="نصف مقدار" onPress={() => onPlannedChange("adjusted")} variant="secondary" />
          <Button disabled={actionBusy} label="نخوردم" onPress={() => onPlannedChange("skipped")} variant="ghost" />
        </View>
      ) : null}
      <Button disabled={actionBusy} label="حذف ثبت" onPress={onDelete} variant="danger" />
    </View>
  );
}

function Metric({ label, target, unit, value }: {
  readonly label: string;
  readonly target?: string;
  readonly unit: string;
  readonly value: string;
}) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricValue}>{value}{unit ? ` ${unit}` : ""}</Text>
      <Text style={styles.mutedText}>{label}</Text>
      {target !== undefined ? <Text style={styles.metricTarget}>هدف برنامه: {target}</Text> : null}
    </View>
  );
}

function stateData<TData>(state: ReturnType<typeof getMobileViewState<TData>>): TData | undefined {
  if (state.status === "loading") return undefined;
  return "data" in state ? state.data : undefined;
}

function displayNutrient(value: number | null | undefined): string {
  return value === null || value === undefined || !Number.isFinite(value)
    ? "—"
    : formatNutritionNumber(Math.round(value));
}

function nutritionTargetLabel(
  estimate: NutritionEstimate | null,
  codes: readonly string[],
  fallbackUnit: string,
): string | undefined {
  if (estimate === null) return undefined;
  const target = codes.map((code) => estimate.targets[code]).find((candidate) => candidate !== undefined);
  if (target === undefined) return undefined;
  const lower = target.minimum ?? target.preferred;
  const upper = target.preferred_maximum ?? target.maximum;
  const unit = fallbackUnit;
  if (lower !== null && upper !== null && lower !== upper) {
    return `${formatNutritionNumber(lower)}–${formatNutritionNumber(upper)} ${unit}`;
  }
  const value = target.preferred ?? target.minimum ?? target.preferred_maximum ?? target.maximum;
  return value === null ? "—" : `${formatNutritionNumber(value)} ${unit}`;
}

function numericValue(value: string): number {
  const normalized = value
    .replace(/[۰-۹]/gu, (digit) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(digit)))
    .replace(/[٠-٩]/gu, (digit) => String("٠١٢٣٤٥٦٧٨٩".indexOf(digit)))
    .replace(/[٬,]/gu, "")
    .replace(/٫/gu, ".");
  return Number(normalized);
}

function todayIsoDate(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function nutritionTrackingError(error: unknown): string {
  return mobileRequestErrorMessage(error, "ثبت تغذیه انجام نشد؛ اتصال و وضعیت برنامه را بررسی کن.");
}

function photoErrorMessage(error: unknown): string {
  if (error instanceof Error && /permission|denied/i.test(error.message)) {
    return "دسترسی دوربین داده نشد یا عکس انتخاب نشد.";
  }
  if (error instanceof Error && /format|size|pixel|orientation|consent/i.test(error.message)) {
    return "فرمت، اندازه یا رضایت عکس برای این عملیات قابل قبول نیست.";
  }
  return mobileRequestErrorMessage(error, "تخمین عکس انجام نشد؛ ثبت دستی همچنان در دسترس است.");
}

function useConnectivityStatus(): ConnectivityStatus {
  const [status, setStatus] = useState<ConnectivityStatus>(connectivityMonitor.getSnapshot().status);
  useEffect(() => connectivityMonitor.subscribe((snapshot) => setStatus(snapshot.status)), []);
  return status;
}

const styles = StyleSheet.create({
  bodyText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  card: {
    gap: fiticianTokens.spacing[3],
    marginTop: fiticianTokens.spacing[3],
  },
  cardTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  checkbox: {
    alignItems: "center",
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    height: 24,
    justifyContent: "center",
    width: 24,
  },
  checkboxChecked: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderColor: fiticianTokens.colors.aqua,
  },
  checkboxMark: {
    color: fiticianTokens.colors.canvas,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "center",
    writingDirection: "ltr",
  },
  choice: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  choiceRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  choiceSelected: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderColor: fiticianTokens.colors.aqua,
  },
  choiceText: {
    color: fiticianTokens.colors.mist,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  choiceTextSelected: {
    color: fiticianTokens.colors.canvas,
  },
  consentRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    minHeight: fiticianTokens.layout.minimumTouchTarget,
  },
  dataStatusRow: {
    borderTopColor: fiticianTokens.colors.line,
    borderTopWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    paddingTop: fiticianTokens.spacing[3],
  },
  dateText: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    writingDirection: "ltr",
  },
  divider: {
    borderTopColor: fiticianTokens.colors.line,
    borderTopWidth: 1,
    marginVertical: fiticianTokens.spacing[2],
  },
  entryCard: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[3],
  },
  entryMeta: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[3],
    justifyContent: "flex-start",
  },
  entryStack: {
    gap: fiticianTokens.spacing[3],
  },
  entryTitle: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  eyebrow: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    letterSpacing: 1,
    textAlign: "right",
    writingDirection: "ltr",
  },
  foodChoice: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    maxWidth: "100%",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  foodChoiceRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  foodChoiceSelected: {
    backgroundColor: fiticianTokens.colors.aqua,
    borderColor: fiticianTokens.colors.aqua,
  },
  foodChoiceText: {
    color: fiticianTokens.colors.mist,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  headingCopy: {
    alignItems: "stretch",
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  inlineFields: {
    alignItems: "center",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
  metric: {
    alignItems: "stretch",
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  metricRow: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
  metricValue: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.lg,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "ltr",
  },
  metricTarget: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  mutedText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  photoActions: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
  },
  photoItem: {
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[2],
    padding: fiticianTokens.spacing[3],
  },
  photoItemActions: {
    flexDirection: "row",
    gap: fiticianTokens.spacing[2],
  },
  photoItems: {
    gap: fiticianTokens.spacing[3],
  },
  photoResult: {
    gap: fiticianTokens.spacing[3],
  },
  section: {
    gap: fiticianTokens.spacing[3],
  },
  sectionHeading: {
    alignItems: "flex-start",
    flexDirection: "row",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  statusText: {
    color: fiticianTokens.colors.success,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "auto",
    writingDirection: "rtl",
  },
  summaryCard: {
    gap: fiticianTokens.spacing[4],
    marginTop: fiticianTokens.spacing[3],
  },
  summaryHeading: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  recentRow: {
    alignItems: "stretch",
    gap: fiticianTokens.spacing[2],
  },
});
