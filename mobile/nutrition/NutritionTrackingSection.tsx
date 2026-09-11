import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as ImagePicker from "expo-image-picker";
import { File } from "expo-file-system";
import { useEffect, useMemo, useRef, useState } from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";

import type { components, MultipartUploadRequest } from "@fitician/core";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { nutritionKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import { useAndroidBackHandler } from "../ui/navigation/BackBehaviorProvider";
import { RTL_LAYOUT, RTL_ROW, RTL_TEXT } from "../ui/rtl";
import {
  AppIcon,
  Button,
  Card,
  Dialog,
  DisclosureCard,
  Notice,
  PageHeading,
  Skeleton,
  TextField,
} from "../ui/components";
import { getMobileViewState, mobileRequestErrorMessage } from "../ui/requestState";
import { fiticianTokens } from "../ui/tokens";
import { UploadCancellationError, UploadManager, type UploadHandle } from "../upload/uploadManager";
import {
  createFoodPhotoUploadJob,
  FOOD_PHOTO_PICKER_OPTIONS,
  nutritionMimeTypeForAsset,
} from "./nutritionUpload";
import { createNutritionCatalogueApi, type FoodCatalogueItem } from "./nutritionCatalogueApi";
import { NutritionAdherenceSection } from "./NutritionAdherenceSection";
import {
  adherencePercentLabel,
  trackingSourceLabel,
  photoEstimatePresentation,
} from "./nutritionTrackingModel";
import {
  createNutritionTrackingApi,
  type NutritionFoodPhotoEstimate,
} from "./nutritionTrackingApi";
import { createNutritionApi } from "./nutritionApi";
import { formatNutritionNumber } from "./nutritionModel";

type CheckInStatus = components["schemas"]["NutritionDailyCheckInStatus"];
type TrackingEntry = components["schemas"]["NutritionTrackingEntryResponse"];
type EntrySource = components["schemas"]["NutritionConsumptionSource"];
type PhotoItem = components["schemas"]["NutritionFoodPhotoItemResponse"];
type EntryMode = "manual" | "photo" | null;
const foodPhotoPollIntervalMs = 2_500;

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
  const [quickCalories, setQuickCalories] = useState("");
  const [entryAmounts, setEntryAmounts] = useState<Record<string, string>>({});
  const [entryToDelete, setEntryToDelete] = useState<TrackingEntry | null>(null);
  const [entryMode, setEntryMode] = useState<EntryMode>(null);
  const [plannedCalories, setPlannedCalories] = useState<number | null>(null);
  const [photoConsent, setPhotoConsent] = useState(false);
  const [photoPreviewUri, setPhotoPreviewUri] = useState<string | null>(null);
  const [photoEstimate, setPhotoEstimate] = useState<NutritionFoodPhotoEstimate | null>(null);
  const [photoHistory, setPhotoHistory] = useState<NutritionFoodPhotoEstimate[]>([]);
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

  useEffect(() => {
    let active = true;
    void api.listPhotoEstimates(20).then((estimates) => {
      if (!active || estimates.length === 0) return;
      setPhotoHistory(estimates);
      setPhotoEstimate((current) => current ?? estimates[0] ?? null);
    }).catch(() => undefined);
    return () => { active = false; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const pendingPhotoEstimateId = photoEstimate?.id;
  const pendingPhotoEstimateStatus = photoEstimate?.status;
  useEffect(() => {
    if (!pendingPhotoEstimateId || (pendingPhotoEstimateStatus !== "queued" && pendingPhotoEstimateStatus !== "analyzing")) {
      return;
    }
    let active = true;
    const poll = async () => {
      try {
        const updated = await api.getPhotoEstimate(pendingPhotoEstimateId);
        if (!active) return;
        setPhotoEstimate(updated);
        setPhotoHistory((current) => upsertPhotoHistory(current, updated));
      } catch {
        // A later interval retries transient network failures.
      }
    };
    const interval = setInterval(() => void poll(), foodPhotoPollIntervalMs);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [pendingPhotoEstimateId, pendingPhotoEstimateStatus]);

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
    if (!Number.isFinite(calories) || calories <= 0) {
      setActionError("یک کالری معتبر وارد کن.");
      return;
    }
    setActionError(null);
    setActionBusy(true);
    try {
      await api.addQuickApproximation({
        calories,
        display_name: "وعده تقریبی",
        entry_date: entryDate,
        protein_g: null,
      });
      setQuickCalories("");
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
      setPhotoPreviewUri(selected.uri);
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
      const queued = await handle.promise;
      setPhotoEstimate(queued);
      setPhotoHistory((current) => upsertPhotoHistory(current, queued));
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
    if (photoEstimate === null || !isPhotoEstimateResult(photoEstimate)) return;
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
      const updated = await api.correctPhotoItem(photoEstimate.id, item.item_id, {
        estimated_amount: amount,
        food_id: foodId,
        remove: false,
      });
      setPhotoEstimate(updated);
      setPhotoHistory((current) => upsertPhotoHistory(current, updated));
    } catch (error) {
      setPhotoError(photoErrorMessage(error));
    } finally {
      setPhotoActionBusy(false);
    }
  }

  async function removePhotoItem(item: PhotoItem): Promise<void> {
    if (photoEstimate === null || !isPhotoEstimateResult(photoEstimate)) return;
    setPhotoActionBusy(true);
    setPhotoError(null);
    try {
      const updated = await api.correctPhotoItem(photoEstimate.id, item.item_id, { remove: true });
      setPhotoEstimate(updated);
      setPhotoHistory((current) => upsertPhotoHistory(current, updated));
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
      setPhotoHistory((current) => upsertPhotoHistory(current, { ...photoEstimate, status: "confirmed", needs_user_confirmation: false }));
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
      setPhotoHistory((current) => current.filter((item) => item.id !== photoEstimate.id));
      setPhotoEstimate(null);
      setPhotoSuccess("برآورد عکس پاک شد.");
    } catch (error) {
      setPhotoError(photoErrorMessage(error));
    } finally {
      setPhotoActionBusy(false);
    }
  }

  function toggleEntryMode(mode: Exclude<EntryMode, null>): void {
    setEntryMode((current) => current === mode ? null : mode);
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
    <View style={[styles.section, RTL_LAYOUT]}>
      <PageHeading eyebrow="امروز" testID="nutrition-tracking-header" title="ثبت تغذیه" />

      <View style={styles.entryHub} testID="nutrition-entry-hub">
        <View style={styles.entryRoot}>
          <View style={styles.entryRootIcon}>
            <AppIcon name="nutrition" color={fiticianTokens.colors.canvas} size={fiticianTokens.iconSize.lg} />
          </View>
          <View style={styles.entryRootCopy}>
            <Text style={styles.entryHubEyebrow}>روش ثبت را انتخاب کن</Text>
            <Text style={styles.entryRootTitle}>ثبت تغذیه</Text>
            <Text style={styles.entryRootSubtitle}>یک روش را برای ثبت وعده انتخاب کن</Text>
          </View>
        </View>
        <View style={styles.entryBranchArea}>
          <View pointerEvents="none" style={styles.entryBranchVertical} />
          <View pointerEvents="none" style={styles.entryBranchHorizontal} />
          <View pointerEvents="none" style={[styles.entryBranchStem, styles.entryBranchStemStart]} />
          <View pointerEvents="none" style={[styles.entryBranchStem, styles.entryBranchStemEnd]} />
          <View style={[styles.entryMethodRow, RTL_ROW]}>
            <EntryMethodButton
              icon="catalogue"
              mode="manual"
              onPress={() => toggleEntryMode("manual")}
              selected={entryMode === "manual"}
              subtitle="غذا را از فهرست انتخاب و مقدار را ثبت کن"
              title="ثبت دستی"
            />
            <EntryMethodButton
              icon="camera"
              mode="photo"
              onPress={() => toggleEntryMode("photo")}
              selected={entryMode === "photo"}
              subtitle="تخمین غذا از روی عکس"
              title="عکس وعده"
            />
          </View>
        </View>
      </View>

      {entryMode === "manual" ? (
        <ManualEntryPanel
          actionBusy={actionBusy}
          catalogueFoods={catalogueFoods}
          catalogueSearch={catalogueSearch}
          catalogueState={catalogueState.status}
          grams={catalogueGrams}
          onAddCatalogue={() => void addCatalogueFood()}
          onAddQuick={() => void addQuickApproximation()}
          onCatalogueSearchChange={setCatalogueSearch}
          onFoodChange={setSelectedFoodId}
          onGramsChange={setCatalogueGrams}
          onQuickCaloriesChange={setQuickCalories}
          onRecentFood={(foodId, grams) => void addRecentFood(foodId, grams)}
          quickCalories={quickCalories}
          recentFoods={recentFoods}
          recentState={recentState.status}
          selectedFoodId={selectedFoodId}
        />
      ) : null}

      {entryMode === "photo" ? (
        <FoodPhotoCard
          actionBusy={photoActionBusy}
          amounts={photoAmounts}
          catalogueFoods={catalogueFoods}
          consent={photoConsent}
          estimate={photoEstimate}
          history={photoHistory}
          foodIds={photoFoodIds}
          onAmountChange={(itemId, amount) => setPhotoAmounts((current) => ({ ...current, [itemId]: amount }))}
          onChooseFood={(itemId, foodId) => setPhotoFoodIds((current) => ({ ...current, [itemId]: foodId }))}
          onClear={() => void clearPhotoEstimate()}
          onConfirm={() => void confirmPhoto()}
          onConsentChange={setPhotoConsent}
          onDeleteItem={(item) => void removePhotoItem(item)}
          onPickCamera={() => void choosePhoto("camera")}
          onPickGallery={() => void choosePhoto("gallery")}
          onCorrectItem={(item) => void correctPhotoItem(item)}
          onSelectHistory={(next) => {
            setPhotoEstimate(next);
            setPhotoPreviewUri(null);
            setPhotoAmounts({});
            setPhotoFoodIds({});
          }}
          previewUri={photoPreviewUri}
          uploading={photoUploading}
        />
      ) : null}

      {(estimateState.status === "error" && estimate === null
        || (entryMode === "manual" && (catalogueState.status === "offline" || catalogueState.status === "stale" || catalogueState.status === "error"))
        || actionError !== null
        || photoError !== null
        || photoSuccess !== null) ? (
        <View style={styles.workflowStatus} testID="nutrition-workflow-status">
          {estimateState.status === "error" && estimate === null ? (
            <Notice compact message="هدف برنامه دریافت نشد؛ ثبت‌های واقعی امروز همچنان در دسترس هستند." variant="warning" />
          ) : null}
          {entryMode === "manual" && (catalogueState.status === "offline" || catalogueState.status === "stale") ? (
            <Notice compact message="فهرست مواد غذایی تازه‌سازی نشده است." variant="offline" />
          ) : null}
          {entryMode === "manual" && catalogueState.status === "error" ? (
            <Notice actionLabel="تلاش دوباره" compact message="فهرست مواد غذایی دریافت نشد." onAction={() => void catalogueQuery.refetch()} variant="danger" />
          ) : null}
          {actionError !== null ? <Notice compact message={actionError} variant="danger" /> : null}
          {photoError !== null ? <Notice compact message={photoError} variant="danger" /> : null}
          {photoSuccess !== null ? <Notice compact message={photoSuccess} variant="success" /> : null}
        </View>
      ) : null}

      <View aria-label="کالری ثبت‌شده" style={styles.dailyPanel} testID="nutrition-daily-panel">
        <View style={styles.dailyCalories}>
          <Text style={styles.dailyLabel}>کالری ثبت‌شده</Text>
          <Text style={styles.dailyValue}>{displayNutrient(daily.actual_totals.energy_kcal ?? daily.actual_totals.calories)}</Text>
          <Text style={styles.dailyPlanned}><Text style={styles.dailyPlannedStrong}>کالری برنامه</Text> · {displayNutrient(plannedCalories)} kcal</Text>
        </View>
        <View style={[styles.metricStrip, RTL_ROW]}>
          <DailyMetric label="پروتئین" value={`${displayNutrient(daily.actual_totals.protein_g)} g`} />
          <View style={styles.metricDivider} />
          <DailyMetric label="ثبت امروز" value={formatNutritionNumber(daily.entries.length)} />
          <View style={styles.metricDivider} />
          <DailyMetric label="کیفیت داده" value={daily.data_status === "sufficient" ? "کافی" : "—"} />
        </View>
      </View>

      {daily.entries.length > 0 ? (
        <Card style={styles.entriesCard} testID="nutrition-today-entries">
          <View style={styles.sectionHeading}>
            <Text style={styles.sectionTitle}>ثبت‌های امروز</Text>
            <Text style={styles.mutedText}>{formatNutritionNumber(visibleEntries.length)} مورد</Text>
          </View>
          <View style={[styles.filterRow, RTL_ROW]}>
            {entrySourceOptions.map((source) => (
              <Pressable
                accessibilityLabel={source === "all" ? "همه" : trackingSourceLabel(source)}
                accessibilityRole="button"
                accessibilityState={{ selected: sourceFilter === source }}
                key={source}
                onPress={() => setSourceFilter(source)}
                style={[styles.filterButton, sourceFilter === source && styles.filterButtonSelected]}
              >
                <Text style={[styles.filterText, sourceFilter === source && styles.filterTextSelected]}>
                  {source === "all" ? "همه" : trackingSourceLabel(source)}
                </Text>
              </Pressable>
            ))}
          </View>
          {visibleEntries.length === 0 ? (
            <View style={styles.filteredEmpty}>
              <Text style={styles.entryTitle}>برای این فیلتر ثبتی نیست.</Text>
            </View>
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
      ) : null}

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

      <View style={styles.adherenceSection} testID="nutrition-adherence">
        <NutritionAdherenceSection embedded onTodayPlannedCaloriesChange={setPlannedCalories} />
      </View>

      <Card style={styles.checkinCard} testID="nutrition-checkin">
        <View style={[styles.checkinHeading, RTL_ROW]}>
          <View style={styles.headingCopy}>
            <Text style={styles.checkinEyebrow}>آخرین مرحله امروز</Text>
            <Text style={styles.checkinTitle}>وضعیت امروز را ثبت کن</Text>
          </View>
          <Text style={styles.optionalBadge}>اختیاری</Text>
        </View>
        <View style={[styles.checkinOptions, RTL_ROW]}>
          {checkInOptions.map((status) => (
            <Pressable
              accessibilityLabel={checkInOptionLabel(status)}
              accessibilityRole="button"
              accessibilityState={{ disabled: actionBusy, selected: checkInValue === status }}
              disabled={actionBusy}
              key={status}
              onPress={() => void saveCheckIn(status)}
              style={[styles.checkinOption, checkInValue === status && styles.checkinOptionSelected]}
            >
              <Text style={[styles.checkinOptionText, checkInValue === status && styles.checkinOptionTextSelected]}>
                {checkInOptionLabel(status)}
              </Text>
            </Pressable>
          ))}
        </View>
      </Card>
    </View>
  );
}

function EntryMethodButton({
  icon,
  mode,
  onPress,
  selected,
  subtitle,
  title,
}: {
  readonly icon: "camera" | "catalogue";
  readonly mode: Exclude<EntryMode, null>;
  readonly onPress: () => void;
  readonly selected: boolean;
  readonly subtitle: string;
  readonly title: string;
}) {
  return (
    <Pressable
      accessibilityLabel={title}
      accessibilityRole="button"
      accessibilityState={{ expanded: selected, selected }}
      accessible
      onPress={onPress}
      style={[styles.entryMethod, selected && styles.entryMethodSelected]}
      testID={`nutrition-entry-method-${mode}`}
    >
      <View style={styles.entryMethodIcon}>
        <AppIcon color={fiticianTokens.colors.aqua} name={icon} size={fiticianTokens.iconSize.md} />
      </View>
      <View style={styles.entryMethodCopy}>
        <Text style={styles.entryMethodTitle}>{title}</Text>
        <Text style={styles.entryMethodSubtitle}>{subtitle}</Text>
      </View>
      <AppIcon color={fiticianTokens.colors.aqua} name={selected ? "chevronUp" : "chevronDown"} size={fiticianTokens.iconSize.sm} />
    </Pressable>
  );
}

function ManualEntryPanel({
  actionBusy,
  catalogueFoods,
  catalogueSearch,
  catalogueState,
  grams,
  onAddCatalogue,
  onAddQuick,
  onCatalogueSearchChange,
  onFoodChange,
  onGramsChange,
  onQuickCaloriesChange,
  onRecentFood,
  quickCalories,
  recentFoods,
  recentState,
  selectedFoodId,
}: {
  readonly actionBusy: boolean;
  readonly catalogueFoods: readonly FoodCatalogueItem[];
  readonly catalogueSearch: string;
  readonly catalogueState: string;
  readonly grams: string;
  readonly onAddCatalogue: () => void;
  readonly onAddQuick: () => void;
  readonly onCatalogueSearchChange: (value: string) => void;
  readonly onFoodChange: (foodId: string) => void;
  readonly onGramsChange: (value: string) => void;
  readonly onQuickCaloriesChange: (value: string) => void;
  readonly onRecentFood: (foodId: string, grams: number | null) => void;
  readonly quickCalories: string;
  readonly recentFoods: readonly components["schemas"]["NutritionRecentFoodResponse"][];
  readonly recentState: string;
  readonly selectedFoodId: string | null;
}) {
  return (
    <Card style={styles.entryPanel} testID="nutrition-manual-entry-panel">
      <View style={styles.panelHeader}>
        <Text style={styles.panelEyebrow}>ثبت دقیق یا سریع</Text>
        <Text style={styles.panelTitle}>ثبت دستی غذا</Text>
        <Text style={styles.panelDescription}>غذا را دقیق از کاتالوگ ثبت کن یا فقط یک برآورد سریع وارد کن.</Text>
      </View>

      {recentFoods.length > 0 ? (
        <View style={styles.recentCard}>
          <View style={[styles.recentHeading, RTL_ROW]}>
            <View style={styles.recentIcon}>
              <AppIcon color={fiticianTokens.colors.aqua} name="foodLog" size={fiticianTokens.iconSize.sm} />
            </View>
            <View style={styles.headingCopy}>
              <Text style={styles.recentTitle}>غذاهای اخیر</Text>
              <Text style={styles.recentSubtitle}>برای ثبت سریع، یکی را انتخاب کن</Text>
            </View>
          </View>
          {recentState === "offline" || recentState === "stale" ? (
            <Notice compact message="غذاهای اخیر از آخرین نسخه ذخیره‌شده نمایش داده می‌شوند." variant="offline" />
          ) : null}
          <View style={styles.recentActions}>
            {recentFoods.map((food) => (
              <Button
                disabled={actionBusy}
                key={food.food_id}
                label={`${food.display_name} · ${formatNutritionNumber(food.last_quantity_grams ?? 100)} گرم`}
                onPress={() => onRecentFood(food.food_id, food.last_quantity_grams)}
                style={styles.recentButton}
                variant="ghost"
              />
            ))}
          </View>
        </View>
      ) : null}

      <View style={styles.formGroup}>
        <Text style={styles.groupTitle}>ثبت دقیق از کاتالوگ</Text>
        <FoodSelector
          foods={catalogueFoods}
          onSearchChange={onCatalogueSearchChange}
          onSelect={onFoodChange}
          searchable
          search={catalogueSearch}
          selectedFoodId={selectedFoodId}
          testID="nutrition-catalogue-selector"
        />
        <TextField
          accessibilityLabel="مقدار به گرم"
          keyboardType="decimal-pad"
          label="مقدار به گرم"
          onChangeText={onGramsChange}
          textDirection="ltr"
          value={grams}
        />
        <Button disabled={actionBusy || selectedFoodId === null} label="ثبت از کاتالوگ" onPress={onAddCatalogue} />
        {catalogueState === "loading" ? <Text style={styles.mutedText}>در حال دریافت فهرست غذا…</Text> : null}
      </View>

      <View style={[styles.formGroup, styles.quickGroup]}>
        <Text style={styles.groupTitle}>ثبت تقریبی سریع</Text>
        <TextField
          accessibilityLabel="کالری تقریبی"
          keyboardType="decimal-pad"
          label="کالری تقریبی"
          onChangeText={onQuickCaloriesChange}
          textDirection="ltr"
          value={quickCalories}
        />
        <Button disabled={actionBusy} label="ثبت تقریبی" onPress={onAddQuick} />
      </View>
    </Card>
  );
}

function FoodSelector({
  foods,
  onSearchChange,
  onSelect,
  searchable = false,
  search,
  selectedFoodId,
  testID,
}: {
  readonly foods: readonly FoodCatalogueItem[];
  readonly onSearchChange?: (value: string) => void;
  readonly onSelect: (foodId: string) => void;
  readonly searchable?: boolean;
  readonly search?: string;
  readonly selectedFoodId: string | null;
  readonly testID?: string;
}) {
  const [open, setOpen] = useState(false);
  const [localSearch, setLocalSearch] = useState("");
  const query = search ?? localSearch;
  const selectedFood = foods.find((food) => food.id === selectedFoodId) ?? null;
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const visibleFoods = foods
    .filter((food) => normalizedQuery.length === 0
      || food.name_fa.toLocaleLowerCase().includes(normalizedQuery)
      || food.name_en.toLocaleLowerCase().includes(normalizedQuery))
    .slice(0, 12);
  const selectorLabel = selectedFood === null ? "انتخاب ماده غذایی" : `ماده غذایی: ${selectedFood.name_fa}`;

  function changeSearch(value: string): void {
    setLocalSearch(value);
    onSearchChange?.(value);
  }

  function selectFood(foodId: string): void {
    onSelect(foodId);
    setOpen(false);
    setLocalSearch("");
    onSearchChange?.("");
  }

  return (
    <View style={styles.selectorField}>
      <Text style={styles.fieldLabel}>انتخاب ماده غذایی</Text>
      <Pressable
        accessibilityLabel={selectorLabel}
        accessibilityRole="button"
        accessibilityState={{ expanded: open, selected: selectedFood !== null }}
        onPress={() => setOpen((current) => !current)}
        style={styles.selectorButton}
        testID={testID}
      >
        <Text style={[styles.selectorText, selectedFood === null && styles.selectorPlaceholder]}>
          {selectedFood?.name_fa ?? "انتخاب کن…"}
        </Text>
        <AppIcon color={fiticianTokens.colors.aqua} name={open ? "chevronUp" : "chevronDown"} size={fiticianTokens.iconSize.sm} />
      </Pressable>
      {open ? (
        <View style={styles.selectorOptions}>
          {searchable ? (
            <TextField
              accessibilityLabel="جستجوی ماده غذایی"
              label="جستجو"
              onChangeText={changeSearch}
              value={query}
            />
          ) : null}
          {visibleFoods.length === 0 ? <Text style={styles.mutedText}>غذایی پیدا نشد.</Text> : null}
          {visibleFoods.map((food) => (
            <Pressable
              accessibilityLabel={food.name_fa}
              accessibilityRole="button"
              accessibilityState={{ selected: selectedFoodId === food.id }}
              key={food.id}
              onPress={() => selectFood(food.id)}
              style={[styles.selectorOption, selectedFoodId === food.id && styles.selectorOptionSelected]}
            >
              <Text style={[styles.selectorOptionText, selectedFoodId === food.id && styles.selectorOptionTextSelected]}>
                {food.name_fa}
              </Text>
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function FoodPhotoCard({
  actionBusy,
  amounts,
  catalogueFoods,
  consent,
  estimate,
  history,
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
  onSelectHistory,
  previewUri,
  uploading,
}: {
  readonly actionBusy: boolean;
  readonly amounts: Readonly<Record<string, string>>;
  readonly catalogueFoods: readonly FoodCatalogueItem[];
  readonly consent: boolean;
  readonly estimate: NutritionFoodPhotoEstimate | null;
  readonly history: readonly NutritionFoodPhotoEstimate[];
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
  readonly onSelectHistory: (estimate: NutritionFoodPhotoEstimate) => void;
  readonly previewUri: string | null;
  readonly uploading: boolean;
}) {
  const presentation = estimate === null ? null : photoEstimatePresentation(estimate);
  const macroTotals = estimate?.macro_totals;
  return (
    <Card style={styles.entryPanel} testID="nutrition-photo-entry-panel">
      <View style={styles.panelHeader}>
        <Text style={styles.panelEyebrow}>تخمین تصویری</Text>
        <Text style={styles.panelTitle}>عکس وعده</Text>
      </View>

      <View style={styles.photoStage}>
        {previewUri === null ? (
          <View style={styles.photoPlaceholder}>
            <AppIcon color={fiticianTokens.colors.aqua} name="camera" size={fiticianTokens.iconSize.xl} />
            <Text style={styles.photoPlaceholderText}>عکس غذا را انتخاب کن</Text>
          </View>
        ) : (
          <Image
            accessibilityLabel="پیش‌نمایش عکس وعده"
            accessible
            resizeMode="cover"
            source={{ uri: previewUri }}
            style={styles.photoPreview}
            testID="nutrition-photo-preview"
          />
        )}
        {uploading ? (
          <View accessible accessibilityLabel="در حال آپلود…" accessibilityRole="progressbar" style={styles.photoBusyOverlay}>
            <Text style={styles.photoBusyText}>در حال آپلود…</Text>
          </View>
        ) : null}
      </View>

      <Text style={styles.photoDisclosure}>عکس فقط برای شناسایی تقریبی غذا از طریق سرویس هوش مصنوعی تنظیم‌شده پردازش می‌شود؛ اطلاعات حساب یا پزشکی همراه آن ارسال نمی‌شود.</Text>
      <Pressable
        accessibilityLabel="با پردازش عکس توسط سرویس ثالث موافقم"
        accessibilityRole="checkbox"
        accessibilityState={{ checked: consent }}
        accessible
        onPress={() => onConsentChange(!consent)}
        style={[styles.consentRow, RTL_ROW]}
      >
        <View style={[styles.checkbox, consent && styles.checkboxChecked]}>
          {consent ? <Text style={styles.checkboxMark}>✓</Text> : null}
        </View>
        <Text style={styles.consentText}>با پردازش عکس توسط سرویس ثالث موافقم</Text>
      </Pressable>

      <View style={[styles.photoActions, RTL_ROW]}>
        <PhotoSourceButton disabled={uploading || !consent} icon="camera" label="گرفتن عکس" onPress={onPickCamera} />
        <PhotoSourceButton disabled={uploading || !consent} icon="foodLog" label="انتخاب از گالری" onPress={onPickGallery} />
      </View>

      {history.length > 0 ? (
        <View style={styles.photoHistory} testID="nutrition-photo-history">
          <View style={[styles.photoHistoryHeader, RTL_ROW]}>
            <Text style={styles.photoHistoryTitle}>سابقه تحلیل عکس</Text>
            <Text style={styles.photoHistoryCount}>{formatNutritionNumber(history.length)}</Text>
          </View>
          <View style={styles.photoHistoryList}>
            {history.map((item) => {
              const itemPresentation = photoEstimatePresentation(item);
              return (
                <Pressable
                  accessibilityLabel={itemPresentation.title}
                  accessibilityRole="button"
                  accessibilityState={{ selected: estimate?.id === item.id }}
                  key={item.id}
                  onPress={() => onSelectHistory(item)}
                  style={[styles.photoHistoryItem, estimate?.id === item.id && styles.photoHistoryItemSelected]}
                >
                  <Text style={styles.photoHistoryItemTitle}>{itemPresentation.title}</Text>
                  <Text style={styles.photoHistoryItemDate}>{formatPhotoHistoryDate(item.created_at) || item.id}</Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      ) : null}

      {estimate !== null && presentation !== null && !isPhotoEstimateResult(estimate) ? (
        <Notice
          compact
          message={presentation.message}
          title={presentation.title}
          variant={estimate.status === "failed" ? "danger" : estimate.status === "expired" || estimate.status === "deleted" ? "warning" : "info"}
        />
      ) : null}

      {estimate !== null && presentation !== null && isPhotoEstimateResult(estimate) ? (
        <View style={styles.photoResult} testID="nutrition-photo-result">
          <View style={styles.photoSummary}>
            <Text style={styles.photoCaloriesLabel}>کالری تخمینی</Text>
            <Text style={styles.photoCaloriesValue}>{displayNutrient(macroTotals?.energy_kcal ?? macroTotals?.calories)} kcal</Text>
            <Text style={styles.photoEstimateBadge}>تخمینی</Text>
            <View style={[styles.photoMacroRow, RTL_ROW]}>
              <PhotoMacro label="پروتئین" value={`${displayNutrient(macroTotals?.protein_g)} g`} />
              <PhotoMacro label="کربوهیدرات" value={`${displayNutrient(macroTotals?.carbohydrate_g)} g`} />
              <PhotoMacro label="چربی" value={`${displayNutrient(macroTotals?.fat_g)} g`} />
            </View>
          </View>
          {!estimate.macro_totals_complete ? (
            <Notice message="برای تکمیل نتیجه، موارد نامشخص را اصلاح یا حذف کن." variant="warning" />
          ) : null}
          <DisclosureCard
            defaultExpanded={false}
            icon="foodLog"
            style={styles.photoDetails}
            summary="موارد شناسایی‌شده را بررسی کن"
            title={`جزئیات تشخیص · ${estimate.items.length} مورد`}
          >
            <View style={styles.photoItems}>
              {estimate.items.map((item) => (
                <PhotoItemCard
                  amounts={amounts}
                  catalogueFoods={catalogueFoods}
                  foodIds={foodIds}
                  item={item}
                  key={item.item_id}
                  onAmountChange={onAmountChange}
                  onChooseFood={onChooseFood}
                  onDelete={onDeleteItem}
                  onCorrect={onCorrectItem}
                  actionBusy={actionBusy}
                />
              ))}
            </View>
          </DisclosureCard>
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

function PhotoSourceButton({
  disabled,
  icon,
  label,
  onPress,
}: {
  readonly disabled: boolean;
  readonly icon: "camera" | "foodLog";
  readonly label: string;
  readonly onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityLabel={label}
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      accessible
      disabled={disabled}
      onPress={onPress}
      style={[styles.photoSourceButton, disabled && styles.photoSourceButtonDisabled]}
    >
      <AppIcon color={disabled ? fiticianTokens.colors.muted : fiticianTokens.colors.aqua} name={icon} size={fiticianTokens.iconSize.sm} />
      <Text style={[styles.photoSourceText, disabled && styles.photoSourceTextDisabled]}>{label}</Text>
    </Pressable>
  );
}

function PhotoMacro({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <View style={styles.photoMacro}>
      <Text style={styles.photoMacroLabel}>{label}</Text>
      <Text style={styles.photoMacroValue}>{value}</Text>
    </View>
  );
}

function PhotoItemCard({
  actionBusy,
  amounts,
  catalogueFoods,
  foodIds,
  item,
  onAmountChange,
  onChooseFood,
  onDelete,
  onCorrect,
}: {
  readonly actionBusy: boolean;
  readonly amounts: Readonly<Record<string, string>>;
  readonly catalogueFoods: readonly FoodCatalogueItem[];
  readonly foodIds: Readonly<Record<string, string>>;
  readonly item: PhotoItem;
  readonly onAmountChange: (itemId: string, value: string) => void;
  readonly onChooseFood: (itemId: string, foodId: string) => void;
  readonly onDelete: (item: PhotoItem) => void;
  readonly onCorrect: (item: PhotoItem) => void;
}) {
  return (
    <View style={styles.photoItem}>
      <View style={[styles.photoItemHeader, RTL_ROW]}>
        <View style={styles.headingCopy}>
          <Text style={styles.entryTitle}>{item.name_guess}</Text>
          <Text style={styles.mutedText}>{item.mapping_status === "resolved" ? "تطبیق‌یافته" : "نیاز به بررسی"}</Text>
        </View>
        <Text style={styles.photoItemConfidence}>اعتماد: {adherencePercentLabel(item.confidence)}</Text>
      </View>
      {item.mapping_status === "unresolved" ? (
        <FoodSelector
          foods={catalogueFoods}
          onSelect={(foodId) => onChooseFood(item.item_id, foodId)}
          selectedFoodId={foodIds[item.item_id] ?? null}
          testID={`nutrition-photo-food-selector-${item.item_id}`}
        />
      ) : null}
      <TextField
        accessibilityLabel={`مقدار ${item.name_guess}`}
        keyboardType="decimal-pad"
        label={`مقدار به ${item.unit === "g" ? "گرم" : item.unit}`}
        onChangeText={(value) => onAmountChange(item.item_id, value)}
        textDirection="ltr"
        value={amounts[item.item_id] ?? String(item.estimated_amount)}
      />
      <View style={[styles.photoItemActions, RTL_ROW]}>
        <Button disabled={actionBusy} label="اعمال اصلاح" onPress={() => onCorrect(item)} variant="secondary" />
        <Button disabled={actionBusy} label="حذف مورد" onPress={() => onDelete(item)} variant="danger" />
      </View>
    </View>
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
      <View style={[styles.sectionHeading, RTL_ROW]}>
        <View style={styles.headingCopy}>
          <Text style={styles.entryTitle}>{entry.display_name}</Text>
          <Text style={styles.mutedText}>{trackingSourceLabel(entry.source)}</Text>
        </View>
        <Text style={styles.statusText}>{entry.user_confirmed ? "تأییدشده" : "تخمینی"}</Text>
      </View>
      <View style={[styles.entryMeta, RTL_ROW]}>
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
        <View style={[styles.photoItemActions, RTL_ROW]}>
          <Button disabled={actionBusy} label="نصف مقدار" onPress={() => onPlannedChange("adjusted")} variant="secondary" />
          <Button disabled={actionBusy} label="نخوردم" onPress={() => onPlannedChange("skipped")} variant="ghost" />
        </View>
      ) : null}
      <Button disabled={actionBusy} label="حذف ثبت" onPress={onDelete} variant="danger" />
    </View>
  );
}

function DailyMetric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <View style={styles.dailyMetric}>
      <Text style={styles.dailyMetricValue}>{value}</Text>
      <Text style={styles.dailyMetricLabel}>{label}</Text>
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

function checkInOptionLabel(status: CheckInStatus): string {
  switch (status) {
    case "on_plan":
      return "طبق برنامه";
    case "mostly_on_plan":
      return "تقریباً طبق برنامه";
    case "off_plan":
      return "خارج از برنامه";
    case "not_recorded":
      return "ثبت نمی‌کنم";
  }
}

function isPhotoEstimateResult(estimate: NutritionFoodPhotoEstimate): boolean {
  return estimate.status === "estimated" || estimate.status === "confirmed";
}

function upsertPhotoHistory(
  history: NutritionFoodPhotoEstimate[],
  estimate: NutritionFoodPhotoEstimate,
): NutritionFoodPhotoEstimate[] {
  const existingIndex = history.findIndex((item) => item.id === estimate.id);
  if (existingIndex === -1) return [estimate, ...history];
  return history.map((item) => (item.id === estimate.id ? estimate : item));
}

function formatPhotoHistoryDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString("fa-IR");
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
  adherenceSection: {
    width: "100%",
  },
  bodyText: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
  },
  checkbox: {
    alignItems: "center",
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    height: fiticianTokens.iconSize.md,
    justifyContent: "center",
    width: fiticianTokens.iconSize.md,
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
  consentRow: {
    alignItems: "center",
    gap: fiticianTokens.spacing[2],
    minHeight: fiticianTokens.layout.minimumTouchTarget,
  },
  consentText: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
  },
  checkinCard: {
    backgroundColor: fiticianTokens.colors.surface,
    gap: fiticianTokens.spacing[3],
    marginTop: 0,
  },
  checkinEyebrow: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
  },
  checkinHeading: {
    alignItems: "center",
    gap: fiticianTokens.spacing[3],
  },
  checkinOption: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    flexBasis: "48%",
    flexGrow: 1,
    justifyContent: "center",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    minWidth: 0,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[2],
  },
  checkinOptionSelected: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.aqua,
  },
  checkinOptionText: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "center",
  },
  checkinOptionTextSelected: {
    color: fiticianTokens.colors.aqua,
  },
  checkinOptions: {
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  checkinTitle: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
  },
  dailyCalories: {
    gap: fiticianTokens.spacing[1],
  },
  dailyLabel: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
  },
  dailyMetric: {
    alignItems: "center",
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
  },
  dailyMetricLabel: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    textAlign: "center",
  },
  dailyMetricValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "center",
    writingDirection: "ltr",
  },
  dailyPanel: {
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[4],
    width: "100%",
  },
  dailyPlanned: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
  },
  dailyPlannedStrong: {
    color: fiticianTokens.colors.ink,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
  },
  dailyValue: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.metric,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    lineHeight: 34,
    writingDirection: "ltr",
  },
  entryBranchArea: {
    marginTop: -fiticianTokens.spacing[3],
    paddingTop: 28,
    position: "relative",
  },
  entryBranchHorizontal: {
    backgroundColor: fiticianTokens.colors.lineStrong,
    height: 1,
    left: "25%",
    position: "absolute",
    right: "25%",
    top: 16,
  },
  entryBranchStem: {
    backgroundColor: fiticianTokens.colors.lineStrong,
    height: 12,
    position: "absolute",
    top: 16,
    width: 1,
  },
  entryBranchStemEnd: {
    right: "25%",
  },
  entryBranchStemStart: {
    left: "25%",
  },
  entryBranchVertical: {
    backgroundColor: fiticianTokens.colors.lineStrong,
    height: 16,
    left: "50%",
    position: "absolute",
    top: 0,
    width: 1,
  },
  entryCard: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[3],
  },
  entryHub: {
    gap: fiticianTokens.spacing[3],
    width: "100%",
  },
  entryHubEyebrow: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
  },
  entryMethod: {
    ...RTL_ROW,
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    elevation: fiticianTokens.shadows.soft.elevation,
    flex: 1,
    gap: fiticianTokens.spacing[2],
    minHeight: 98,
    minWidth: 0,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[3],
    shadowColor: fiticianTokens.shadows.soft.color,
    shadowOffset: fiticianTokens.shadows.soft.offset,
    shadowOpacity: fiticianTokens.shadows.soft.opacity,
    shadowRadius: fiticianTokens.shadows.soft.radius,
  },
  entryMethodCopy: {
    alignItems: "stretch",
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
  },
  entryMethodIcon: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    height: 40,
    justifyContent: "center",
    width: 40,
  },
  entryMethodRow: {
    gap: fiticianTokens.spacing[2],
    width: "100%",
  },
  entryMethodSelected: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.aqua,
    shadowColor: fiticianTokens.colors.aqua,
    shadowOpacity: fiticianTokens.shadows.glow.opacity,
  },
  entryMethodSubtitle: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    lineHeight: 16,
  },
  entryMethodTitle: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
  },
  entryMeta: {
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  entryPanel: {
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.lineStrong,
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[3],
    width: "100%",
  },
  entryRoot: {
    ...RTL_ROW,
    alignItems: "center",
    alignSelf: "center",
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.large,
    borderWidth: 1,
    elevation: fiticianTokens.shadows.soft.elevation,
    gap: fiticianTokens.spacing[3],
    justifyContent: "center",
    maxWidth: 368,
    minHeight: 80,
    paddingHorizontal: fiticianTokens.spacing[4],
    paddingVertical: fiticianTokens.spacing[3],
    shadowColor: fiticianTokens.shadows.soft.color,
    shadowOffset: fiticianTokens.shadows.soft.offset,
    shadowOpacity: fiticianTokens.shadows.soft.opacity,
    shadowRadius: fiticianTokens.shadows.soft.radius,
    width: "100%",
  },
  entryRootCopy: {
    alignItems: "stretch",
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
  },
  entryRootIcon: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.aqua,
    borderRadius: fiticianTokens.radii.small,
    height: 44,
    justifyContent: "center",
    width: 44,
  },
  entryRootSubtitle: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
  },
  entryRootTitle: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 26,
  },
  entryStack: {
    gap: fiticianTokens.spacing[3],
  },
  entryTitle: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
  },
  entriesCard: {
    gap: fiticianTokens.spacing[3],
    marginTop: 0,
    width: "100%",
  },
  fieldLabel: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.medium,
  },
  filterButton: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    minHeight: 40,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  filterButtonSelected: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
  },
  filterRow: {
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  filterText: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
  },
  filterTextSelected: {
    color: fiticianTokens.colors.aqua,
  },
  filteredEmpty: {
    alignItems: "center",
    paddingVertical: fiticianTokens.spacing[4],
  },
  formGroup: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[3],
  },
  groupTitle: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
  },
  headingCopy: {
    alignItems: "stretch",
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
  },
  inlineFields: {
    ...RTL_ROW,
    alignItems: "center",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[3],
  },
  metricDivider: {
    backgroundColor: fiticianTokens.colors.line,
    height: "70%",
    width: 1,
  },
  metricStrip: {
    alignItems: "stretch",
    borderTopColor: fiticianTokens.colors.line,
    borderTopWidth: 1,
    gap: fiticianTokens.spacing[2],
    paddingTop: fiticianTokens.spacing[3],
  },
  mutedText: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
  },
  optionalBadge: {
    ...RTL_TEXT,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.pill,
    borderWidth: 1,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[1],
  },
  panelDescription: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
  },
  panelEyebrow: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
  },
  panelHeader: {
    gap: fiticianTokens.spacing[1],
  },
  panelTitle: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
  },
  photoActions: {
    gap: fiticianTokens.spacing[2],
  },
  photoBusyOverlay: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.scrim,
    bottom: 0,
    justifyContent: "center",
    left: 0,
    position: "absolute",
    right: 0,
    top: 0,
  },
  photoBusyText: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
  },
  photoCaloriesLabel: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
  },
  photoCaloriesValue: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.metric,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    writingDirection: "ltr",
  },
  photoDetails: {
    marginTop: 0,
  },
  photoDisclosure: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
  },
  photoEstimateBadge: {
    ...RTL_TEXT,
    alignSelf: "flex-start",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderRadius: fiticianTokens.radii.pill,
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[1],
  },
  photoHistory: {
    borderTopColor: fiticianTokens.colors.line,
    borderTopWidth: 1,
    gap: fiticianTokens.spacing[2],
    paddingTop: fiticianTokens.spacing[3],
  },
  photoHistoryCount: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
  },
  photoHistoryHeader: {
    alignItems: "center",
    justifyContent: "space-between",
  },
  photoHistoryItem: {
    ...RTL_ROW,
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.canvas,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    justifyContent: "space-between",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  photoHistoryItemDate: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
  },
  photoHistoryItemSelected: {
    borderColor: fiticianTokens.colors.aqua,
  },
  photoHistoryItemTitle: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.ink,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
  },
  photoHistoryList: {
    gap: fiticianTokens.spacing[2],
  },
  photoHistoryTitle: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
  },
  photoItem: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[3],
  },
  photoItemActions: {
    gap: fiticianTokens.spacing[2],
  },
  photoItemConfidence: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
  },
  photoItemHeader: {
    alignItems: "flex-start",
    gap: fiticianTokens.spacing[2],
  },
  photoItems: {
    gap: fiticianTokens.spacing[3],
  },
  photoMacro: {
    backgroundColor: fiticianTokens.colors.surfaceHighlight,
    borderRadius: fiticianTokens.radii.small,
    flex: 1,
    gap: fiticianTokens.spacing[1],
    minWidth: 0,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[2],
  },
  photoMacroLabel: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
    textAlign: "center",
  },
  photoMacroRow: {
    gap: fiticianTokens.spacing[2],
    marginTop: fiticianTokens.spacing[3],
  },
  photoMacroValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "center",
    writingDirection: "ltr",
  },
  photoPlaceholder: {
    alignItems: "center",
    gap: fiticianTokens.spacing[2],
    justifyContent: "center",
  },
  photoPlaceholderText: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
  },
  photoPreview: {
    height: "100%",
    width: "100%",
  },
  photoResult: {
    gap: fiticianTokens.spacing[3],
  },
  photoSourceButton: {
    ...RTL_ROW,
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    flex: 1,
    gap: fiticianTokens.spacing[2],
    justifyContent: "center",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    minWidth: 0,
    paddingHorizontal: fiticianTokens.spacing[2],
    paddingVertical: fiticianTokens.spacing[2],
  },
  photoSourceButtonDisabled: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    opacity: 0.65,
  },
  photoSourceText: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
  },
  photoSourceTextDisabled: {
    color: fiticianTokens.colors.muted,
  },
  photoStage: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.canvas,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    height: 220,
    justifyContent: "center",
    overflow: "hidden",
    position: "relative",
    width: "100%",
  },
  photoSummary: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.lineStrong,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[1],
    padding: fiticianTokens.spacing[3],
  },
  quickGroup: {
    backgroundColor: fiticianTokens.colors.infoSurface,
    borderColor: fiticianTokens.colors.lineStrong,
  },
  recentActions: {
    gap: fiticianTokens.spacing[2],
  },
  recentButton: {
    alignSelf: "stretch",
    borderRadius: fiticianTokens.radii.small,
  },
  recentCard: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[3],
    padding: fiticianTokens.spacing[3],
  },
  recentHeading: {
    alignItems: "center",
    gap: fiticianTokens.spacing[2],
  },
  recentIcon: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderRadius: fiticianTokens.radii.small,
    height: 32,
    justifyContent: "center",
    width: 32,
  },
  recentSubtitle: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: 10,
  },
  recentTitle: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    fontWeight: fiticianTokens.typography.fontWeight.extraBold,
  },
  section: {
    gap: fiticianTokens.spacing[3],
    paddingBottom: fiticianTokens.spacing[8],
    width: "100%",
  },
  sectionHeading: {
    ...RTL_ROW,
    alignItems: "flex-start",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  sectionTitle: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.displayPersian,
    fontSize: fiticianTokens.typography.fontSize.h3,
    lineHeight: 28,
  },
  selectorButton: {
    ...RTL_ROW,
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.canvas,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    justifyContent: "space-between",
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  selectorField: {
    gap: fiticianTokens.spacing[2],
  },
  selectorOption: {
    ...RTL_LAYOUT,
    backgroundColor: fiticianTokens.colors.surface,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    minHeight: fiticianTokens.layout.minimumTouchTarget,
    paddingHorizontal: fiticianTokens.spacing[3],
    paddingVertical: fiticianTokens.spacing[2],
  },
  selectorOptionSelected: {
    backgroundColor: fiticianTokens.colors.surfaceInteractive,
    borderColor: fiticianTokens.colors.aqua,
  },
  selectorOptionText: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
  },
  selectorOptionTextSelected: {
    color: fiticianTokens.colors.aqua,
  },
  selectorOptions: {
    backgroundColor: fiticianTokens.colors.surfaceRaised,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[2],
    padding: fiticianTokens.spacing[2],
  },
  selectorPlaceholder: {
    color: fiticianTokens.colors.muted,
  },
  selectorText: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.ink,
    flex: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
  },
  statusText: {
    ...RTL_TEXT,
    color: fiticianTokens.colors.success,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
  },
  workflowStatus: {
    gap: fiticianTokens.spacing[2],
    width: "100%",
  },
});
