import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as DocumentPicker from "expo-document-picker";
import * as ImagePicker from "expo-image-picker";
import { File } from "expo-file-system";
import { useEffect, useMemo, useState } from "react";
import { Linking, StyleSheet, Text, View } from "react-native";

import { ApiError, type MultipartUploadRequest } from "@fitician/core";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { nutritionKeys } from "../data/queryKeys";
import { connectivityMonitor, type ConnectivityStatus } from "../platform/connectivity";
import { ExpoPrivateMediaStore } from "../media/privateMediaStore";
import { useAndroidBackHandler } from "../ui/navigation/BackBehaviorProvider";
import {
  Button,
  Card,
  Dialog,
  DisclosureCard,
  EmptyState,
  Notice,
  PageHeading,
  SegmentedControl,
  Skeleton,
  TextField,
} from "../ui/components";
import { getMobileViewState } from "../ui/requestState";
import { fiticianTokens } from "../ui/tokens";
import { UploadCancellationError, UploadManager, type UploadHandle } from "../upload/uploadManager";
import {
  createLabDocumentUploadJob,
  LAB_DOCUMENT_MIME_TYPES,
  labMimeTypeForAsset,
  type NutritionLabAsset,
} from "./nutritionUpload";
import {
  labRequestStatusLabel,
  labReviewStatusLabel,
  supplementSafetyPresentation,
  supplementStatusLabel,
} from "./nutritionClinicalModel";
import {
  createNutritionTrackingApi,
  type NutritionLabDocument,
  type NutritionLabRequest,
  type NutritionLabUpload,
  type NutritionSupplementCatalogue,
  type NutritionSupplementOrder,
} from "./nutritionTrackingApi";
import { formatNutritionNumber } from "./nutritionModel";

type LabSelection = {
  readonly asset: NutritionLabAsset;
  readonly name: string;
};

type SupplementStatusFilter = "all" | "prescribed" | "active" | "completed" | "discontinued";

const supplementStatusFilters: readonly { readonly label: string; readonly value: SupplementStatusFilter }[] = [
  { label: "همه", value: "all" },
  { label: "تجویزشده", value: "prescribed" },
  { label: "فعال", value: "active" },
  { label: "تمام‌شده", value: "completed" },
  { label: "متوقف‌شده", value: "discontinued" },
];

export function NutritionClinicalSection() {
  const auth = useMobileAuth();
  const queryClient = useQueryClient();
  const connectivityStatus = useConnectivityStatus();
  const api = useMemo(
    () => createNutritionTrackingApi(auth.request, auth.download),
    [auth.download, auth.request],
  );
  const labsQuery = useQuery({
    queryFn: api.getLabDocuments,
    queryKey: nutritionKeys.labs(),
  });
  const requestsQuery = useQuery({
    queryFn: api.getLabRequests,
    queryKey: nutritionKeys.labRequests(),
  });
  const ordersQuery = useQuery({
    queryFn: api.getSupplementOrders,
    queryKey: nutritionKeys.supplementOrders(),
  });
  const catalogueQuery = useQuery({
    queryFn: api.getSupplementCatalogue,
    queryKey: nutritionKeys.supplementCatalogue(),
  });
  const labsState = getMobileViewState(labsQuery, { connectivityStatus });
  const requestsState = getMobileViewState(requestsQuery, { connectivityStatus });
  const ordersState = getMobileViewState(ordersQuery, { connectivityStatus });
  const catalogueState = getMobileViewState(catalogueQuery, { connectivityStatus });
  const labs = stateData(labsState) ?? [];
  const requests = stateData(requestsState) ?? [];
  const orders = stateData(ordersState) ?? [];
  const catalogue = stateData(catalogueState) ?? [];
  const [supplementStatusFilter, setSupplementStatusFilter] = useState<SupplementStatusFilter>("all");
  const visibleOrders = orders.filter(
    (order) => supplementStatusFilter === "all" || order.status === supplementStatusFilter,
  );
  const upload = auth.upload;
  const [testDate, setTestDate] = useState("");
  const [laboratoryName, setLaboratoryName] = useState("");
  const [category, setCategory] = useState("");
  const [userNote, setUserNote] = useState("");
  const [selectedFile, setSelectedFile] = useState<LabSelection | null>(null);
  const [labUploadKey, setLabUploadKey] = useState<string | undefined>();
  const [labUploadError, setLabUploadError] = useState<string | null>(null);
  const [labUploadNotice, setLabUploadNotice] = useState<string | null>(null);
  const [labUploading, setLabUploading] = useState(false);
  const [labUploadRef, setLabUploadRef] = useState<UploadHandle<NutritionLabUpload> | null>(null);
  const [documentBusyId, setDocumentBusyId] = useState<string | null>(null);
  const [documentError, setDocumentError] = useState<string | null>(null);
  const [documentToDelete, setDocumentToDelete] = useState<NutritionLabDocument | null>(null);
  const [supplementError, setSupplementError] = useState<string | null>(null);

  const uploadManager = useMemo(
    () => new UploadManager({
      executor: async <TResponse,>(request: MultipartUploadRequest) => upload<TResponse>(request),
    }),
    [upload],
  );

  useAndroidBackHandler(
    "upload",
    () => {
      if (labUploadRef === null || !labUploading) return false;
      labUploadRef.cancel();
      return true;
    },
    labUploading,
  );

  async function uploadLabSelection(
    selection: LabSelection,
    retryKey: string | undefined = labUploadKey,
  ): Promise<void> {
    if (connectivityStatus === "offline") {
      setLabUploadError("بارگذاری پرونده آزمایش در حالت آفلاین انجام نمی‌شود.");
      return;
    }
    setLabUploadError(null);
    setLabUploadNotice(null);
    const requestId = requests.find((request) => request.status === "requested")?.id;
    try {
      const handle = uploadManager.enqueue<NutritionLabUpload>(createLabDocumentUploadJob({
        asset: selection.asset,
        idempotencyKey: retryKey,
        metadata: {
          category: optionalText(category),
          laboratoryName: optionalText(laboratoryName),
          requestId,
          testDate: optionalText(testDate),
          userNote: optionalText(userNote),
        },
      }));
      setLabUploadKey(handle.idempotencyKey);
      setLabUploadRef(handle);
      setLabUploading(true);
      const result = await handle.promise;
      setLabUploadNotice(result.duplicate
        ? "این فایل قبلاً در پرونده سلامتت ثبت شده بود؛ همان سابقه استفاده شد."
        : "فایل آزمایش با موفقیت در پرونده خصوصی تو ثبت شد.");
      setSelectedFile(null);
      setLabUploadKey(undefined);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: nutritionKeys.labs() }),
        queryClient.invalidateQueries({ queryKey: nutritionKeys.labRequests() }),
      ]);
    } catch (error) {
      if (!(error instanceof UploadCancellationError)) {
        setLabUploadError(clinicalErrorMessage(error));
      }
    } finally {
      setLabUploadRef(null);
      setLabUploading(false);
    }
  }

  async function chooseLabFile(source: "image" | "document"): Promise<void> {
    setLabUploadError(null);
    setLabUploadNotice(null);
    try {
      if (source === "document") {
        const result = await DocumentPicker.getDocumentAsync({
          base64: false,
          copyToCacheDirectory: true,
          multiple: false,
          type: [...LAB_DOCUMENT_MIME_TYPES],
        });
        if (result.canceled) return;
        const selected = result.assets[0];
        if (selected === undefined) throw new Error("No laboratory document was selected");
        const mimeType = labMimeTypeForAsset(selected.mimeType, selected.name);
        if (mimeType === null) throw new Error("Unsupported laboratory document format");
        const selection: LabSelection = {
          asset: {
            bytes: new Uint8Array(await new File(selected.uri).arrayBuffer()),
            filename: selected.name,
            mimeType,
          },
          name: selected.name,
        };
        setSelectedFile(selection);
        setLabUploadKey(undefined);
        await uploadLabSelection(selection, undefined);
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        allowsEditing: false,
        base64: false,
        exif: true,
        mediaTypes: ["images"],
      });
      if (result.canceled) return;
      const selected = result.assets[0];
      if (selected === undefined) throw new Error("No laboratory image was selected");
      const mimeType = labMimeTypeForAsset(selected.mimeType, selected.uri);
      if (mimeType === null || mimeType === "application/pdf") {
        throw new Error("Unsupported laboratory image format");
      }
      const orientation = selected.exif?.Orientation;
      const selection: LabSelection = {
        asset: {
          bytes: new Uint8Array(await new File(selected.uri).arrayBuffer()),
          filename: labFilenameForMimeType(mimeType),
          height: selected.height,
          mimeType,
          orientation: typeof orientation === "number" ? orientation : null,
          width: selected.width,
        },
        name: labFilenameForMimeType(mimeType),
      };
      setSelectedFile(selection);
      setLabUploadKey(undefined);
      await uploadLabSelection(selection, undefined);
    } catch (error) {
      if (!(error instanceof UploadCancellationError)) {
        setLabUploadError(clinicalErrorMessage(error));
      }
    }
  }

  async function openLab(document: NutritionLabDocument): Promise<void> {
    const user = auth.user;
    if (user === null) {
      setDocumentError("برای مشاهده پرونده، ابتدا وارد حساب کاربری شو.");
      return;
    }
    setDocumentError(null);
    setDocumentBusyId(document.id);
    try {
      const grant = await api.grantLabAccess(document.id);
      const privateUrl = new URL(grant.access_url, "https://fitician.invalid");
      const token = privateUrl.searchParams.get("token");
      if (token === null || token.length === 0) throw new Error("Private laboratory access was not granted");
      const download = await api.downloadLabDocument(document.id, token);
      const stored = await new ExpoPrivateMediaStore().save(
        user.id,
        `lab-${document.id}.${document.content_type === "application/pdf" ? "pdf" : "jpg"}`,
        download,
      );
      await Linking.openURL(stored.uri);
    } catch (error) {
      setDocumentError(clinicalErrorMessage(error, "فایل خصوصی آزمایش باز نشد؛ دوباره تلاش کن."));
    } finally {
      setDocumentBusyId(null);
    }
  }

  async function deleteLab(document: NutritionLabDocument): Promise<void> {
    setDocumentError(null);
    setDocumentBusyId(document.id);
    try {
      await api.deleteLabDocument(document.id);
      setDocumentToDelete(null);
      await queryClient.invalidateQueries({ queryKey: nutritionKeys.labs() });
    } catch (error) {
      setDocumentError(clinicalErrorMessage(error, "حذف پرونده آزمایش انجام نشد."));
    } finally {
      setDocumentBusyId(null);
    }
  }

  async function acknowledge(order: NutritionSupplementOrder): Promise<void> {
    const safety = supplementSafetyPresentation(order.combined_exposure_safety);
    if (safety.blocked) {
      setSupplementError(safety.message);
      return;
    }
    setSupplementError(null);
    try {
      await api.acknowledgeSupplementOrder(order.id, { adherence_note: null });
      await queryClient.invalidateQueries({ queryKey: nutritionKeys.supplementOrders() });
    } catch (error) {
      setSupplementError(clinicalErrorMessage(error, "تأیید دستور مکمل انجام نشد."));
    }
  }

  return (
    <View style={styles.section}>
      <PageHeading
        eyebrow="پرونده سلامت"
        supportingText="مدارک آزمایش و دستورهای ثبت‌شده را در فضای عضو و با کنترل ایمنی دنبال کن."
        title="آزمایش‌ها و مکمل‌ها"
      />

      <LabUploadCard
        category={category}
        error={labUploadError}
        laboratoryName={laboratoryName}
        loading={labUploading}
        notice={labUploadNotice}
        onCategoryChange={setCategory}
        onChooseImage={() => void chooseLabFile("image")}
        onChooseDocument={() => void chooseLabFile("document")}
        onLaboratoryNameChange={setLaboratoryName}
        onRetry={selectedFile === null ? undefined : () => void uploadLabSelection(selectedFile)}
        onTestDateChange={setTestDate}
        onNoteChange={setUserNote}
        note={userNote}
        selectedFile={selectedFile}
        testDate={testDate}
        disabled={labUploading || connectivityStatus === "offline"}
      />

      <LabRequestsCard requests={requests} state={requestsState} />
      <LabDocumentsCard
        documents={labs}
        error={documentError}
        state={labsState}
        busyId={documentBusyId}
        onDelete={setDocumentToDelete}
        onOpen={(document) => void openLab(document)}
        onRetry={() => void labsQuery.refetch()}
      />

      <SupplementOrdersCard
        error={supplementError}
        onAcknowledge={(order) => void acknowledge(order)}
        onStatusFilterChange={setSupplementStatusFilter}
        onRetry={() => void ordersQuery.refetch()}
        orders={visibleOrders}
        state={ordersState}
        statusFilter={supplementStatusFilter}
        totalOrders={orders.length}
      />
      {catalogue.length > 0 ? <VerifiedSupplementCatalogue items={catalogue} state={catalogueState} /> : null}

      <Dialog
        cancelLabel="انصراف"
        confirmLabel="حذف پرونده"
        destructive
        message={documentToDelete === null ? "" : `پرونده «${documentToDelete.original_filename}» حذف شود؟`}
        onCancel={() => setDocumentToDelete(null)}
        onClose={() => setDocumentToDelete(null)}
        onConfirm={documentToDelete === null ? undefined : () => void deleteLab(documentToDelete)}
        title="حذف پرونده آزمایش"
        visible={documentToDelete !== null}
      />
    </View>
  );
}

function LabUploadCard({
  category,
  disabled,
  error,
  laboratoryName,
  loading,
  notice,
  note,
  onCategoryChange,
  onChooseDocument,
  onChooseImage,
  onLaboratoryNameChange,
  onNoteChange,
  onRetry,
  onTestDateChange,
  selectedFile,
  testDate,
}: {
  readonly category: string;
  readonly disabled: boolean;
  readonly error: string | null;
  readonly laboratoryName: string;
  readonly loading: boolean;
  readonly notice: string | null;
  readonly note: string;
  readonly onCategoryChange: (value: string) => void;
  readonly onChooseDocument: () => void;
  readonly onChooseImage: () => void;
  readonly onLaboratoryNameChange: (value: string) => void;
  readonly onNoteChange: (value: string) => void;
  readonly onRetry?: () => void;
  readonly onTestDateChange: (value: string) => void;
  readonly selectedFile: LabSelection | null;
  readonly testDate: string;
}) {
  return (
    <Card style={styles.card}>
      <Text style={styles.cardTitle}>افزودن نتیجه آزمایش</Text>
      <Text style={styles.bodyText}>PDF یا تصویر JPG/PNG با حجم و محتوای معتبر انتخاب کن. فایل فقط در پرونده خصوصی خودت ذخیره می‌شود.</Text>
      <View style={styles.formStack}>
        <TextField
          accessibilityLabel="تاریخ آزمایش"
          label="تاریخ آزمایش"
          onChangeText={onTestDateChange}
          placeholder="YYYY-MM-DD"
          textDirection="ltr"
          value={testDate}
        />
        <TextField
          accessibilityLabel="نام آزمایشگاه"
          label="نام آزمایشگاه"
          onChangeText={onLaboratoryNameChange}
          value={laboratoryName}
        />
        <TextField
          accessibilityLabel="دسته‌بندی آزمایش"
          label="دسته‌بندی"
          onChangeText={onCategoryChange}
          value={category}
        />
        <TextField
          accessibilityLabel="یادداشت آزمایش"
          label="یادداشت"
          multiline
          numberOfLines={3}
          onChangeText={onNoteChange}
          style={styles.multiline}
          value={note}
        />
      </View>
      <View style={styles.actions}>
        <Button disabled={disabled} label="انتخاب PDF" loading={loading} onPress={onChooseDocument} variant="primary" />
        <Button disabled={disabled} label="انتخاب تصویر" onPress={onChooseImage} variant="secondary" />
      </View>
      {selectedFile !== null ? <Text style={styles.fileName}>فایل انتخاب‌شده: {selectedFile.name}</Text> : null}
      {error !== null ? <Notice actionLabel={onRetry ? "تلاش دوباره" : undefined} message={error} onAction={onRetry} variant="danger" /> : null}
      {notice !== null ? <Notice message={notice} variant="success" /> : null}
      {disabled && !loading ? <Notice message="برای بارگذاری پرونده آزمایش به اینترنت وصل شو." variant="offline" /> : null}
    </Card>
  );
}

function LabRequestsCard({
  requests,
  state,
}: {
  readonly requests: readonly NutritionLabRequest[];
  readonly state: ReturnType<typeof getMobileViewState<NutritionLabRequest[]>>;
}) {
  if (state.status === "loading") return <Skeleton height={150} />;
  if (state.status === "offline" && requests.length === 0) {
    return <Notice message="درخواست‌های آزمایش برای مشاهده به اینترنت نیاز دارند." variant="offline" />;
  }
  return (
    <Card style={styles.card}>
      <Text style={styles.cardTitle}>درخواست‌های آزمایش</Text>
      {state.status === "offline" || state.status === "stale" ? <Notice message="آخرین درخواست‌های ذخیره‌شده نمایش داده می‌شوند." variant="offline" /> : null}
      {requests.length === 0 ? (
        <EmptyState title="درخواستی ثبت نشده است">اگر پزشک آزمایشی درخواست کند، اینجا نمایش داده می‌شود.</EmptyState>
      ) : (
        <View style={styles.itemStack}>
          {requests.map((request) => (
            <View key={request.id} style={styles.itemCard}>
              <View style={styles.rowBetween}>
                <Text style={styles.statusText}>{labRequestStatusLabel(request.status)}</Text>
                <Text style={styles.itemTitle}>{request.requested_tests.join("، ")}</Text>
              </View>
              {request.user_visible_reason ? <Text style={styles.bodyText}>{request.user_visible_reason}</Text> : null}
            </View>
          ))}
        </View>
      )}
    </Card>
  );
}

function LabDocumentsCard({
  busyId,
  documents,
  error,
  onDelete,
  onOpen,
  onRetry,
  state,
}: {
  readonly busyId: string | null;
  readonly documents: readonly NutritionLabDocument[];
  readonly error: string | null;
  readonly onDelete: (document: NutritionLabDocument) => void;
  readonly onOpen: (document: NutritionLabDocument) => void;
  readonly onRetry: () => void;
  readonly state: ReturnType<typeof getMobileViewState<NutritionLabDocument[]>>;
}) {
  if (state.status === "loading") return <Skeleton height={280} />;
  if (state.status === "error" && documents.length === 0) {
    return <Notice actionLabel="تلاش دوباره" message="پرونده‌های آزمایش دریافت نشدند." onAction={onRetry} variant="danger" />;
  }
  if (state.status === "offline" && documents.length === 0) {
    return <Notice message="برای مشاهده پرونده‌های آزمایش به اینترنت وصل شو." variant="offline" />;
  }
  return (
    <Card style={styles.card}>
      <View style={styles.rowBetween}>
        <Text style={styles.count}>{formatNutritionNumber(documents.length)} فایل</Text>
        <Text style={styles.cardTitle}>پرونده‌های آزمایش</Text>
      </View>
      {state.status === "offline" || state.status === "stale" ? <Notice message="آخرین فهرست پرونده‌ها نمایش داده می‌شود." variant="offline" /> : null}
      {error !== null ? <Notice message={error} variant="danger" /> : null}
      {documents.length === 0 ? (
        <EmptyState title="هنوز پرونده‌ای ثبت نشده است">اولین نتیجه آزمایش را از فرم بالا اضافه کن.</EmptyState>
      ) : (
        <View style={styles.itemStack}>
          {documents.map((document) => (
            <View key={document.id} style={styles.itemCard}>
              <View style={styles.rowBetween}>
                <Text style={styles.statusText}>{labReviewStatusLabel(document.review_status)}</Text>
                <View style={styles.headingCopy}>
                  <Text style={styles.itemTitle}>{document.original_filename}</Text>
                  <Text style={styles.mutedText}>{document.content_type} · {formatBytes(document.byte_size)}</Text>
                </View>
              </View>
              <View style={styles.metaStack}>
                <Text style={styles.mutedText}>تاریخ: {document.test_date ?? "ثبت نشده"}</Text>
                <Text style={styles.mutedText}>آزمایشگاه: {document.laboratory_name ?? "ثبت نشده"}</Text>
                {document.category ? <Text style={styles.mutedText}>دسته‌بندی: {document.category}</Text> : null}
              </View>
              {document.user_note || document.review_notes ? <Text style={styles.bodyText}>{document.user_note ?? document.review_notes}</Text> : null}
              <View style={styles.actions}>
                <Button disabled={busyId !== null} label="مشاهده امن" onPress={() => onOpen(document)} variant="secondary" />
                <Button disabled={busyId !== null} label="حذف" onPress={() => onDelete(document)} variant="danger" />
              </View>
            </View>
          ))}
        </View>
      )}
    </Card>
  );
}

function SupplementOrdersCard({
  error,
  onAcknowledge,
  onStatusFilterChange,
  onRetry,
  orders,
  state,
  statusFilter,
  totalOrders,
}: {
  readonly error: string | null;
  readonly onAcknowledge: (order: NutritionSupplementOrder) => void;
  readonly onStatusFilterChange: (value: SupplementStatusFilter) => void;
  readonly onRetry: () => void;
  readonly orders: readonly NutritionSupplementOrder[];
  readonly state: ReturnType<typeof getMobileViewState<NutritionSupplementOrder[]>>;
  readonly statusFilter: SupplementStatusFilter;
  readonly totalOrders: number;
}) {
  if (state.status === "loading") return <Skeleton height={300} />;
  if (state.status === "error" && orders.length === 0) {
    return <Notice actionLabel="تلاش دوباره" message="دستورهای مکمل دریافت نشدند." onAction={onRetry} variant="danger" />;
  }
  if (state.status === "offline" && orders.length === 0) {
    return <Notice message="برای مشاهده دستورهای مکمل به اینترنت وصل شو." variant="offline" />;
  }
  return (
    <Card style={styles.card}>
      <View style={styles.rowBetween}>
        <Text style={styles.count}>{formatNutritionNumber(orders.length)} مورد</Text>
        <Text style={styles.cardTitle}>مکمل‌های من</Text>
      </View>
      <SegmentedControl
        accessibilityLabel="فیلتر وضعیت مکمل"
        onChange={(value) => {
          if (supplementStatusFilters.some((option) => option.value === value)) {
            onStatusFilterChange(value as SupplementStatusFilter);
          }
        }}
        options={supplementStatusFilters}
        selectedValue={statusFilter}
        testID="supplement-status-filter"
      />
      {state.status === "offline" || state.status === "stale" ? <Notice message="آخرین دستورهای ذخیره‌شده نمایش داده می‌شوند." variant="offline" /> : null}
      {error !== null ? <Notice message={error} variant="danger" /> : null}
      {orders.length === 0 ? (
        <EmptyState title={totalOrders === 0 ? "دستور مکملی ثبت نشده است" : "موردی با این وضعیت نیست"}>
          {totalOrders === 0
            ? "دستورهای عضو فقط از مسیر بررسی و ثبت مسئول سلامت نمایش داده می‌شوند."
            : "فیلتر دیگری را برای مشاهده دستورهای ثبت‌شده انتخاب کن."}
        </EmptyState>
      ) : (
        <View style={styles.itemStack}>
          {orders.map((order) => {
            const safety = supplementSafetyPresentation(order.combined_exposure_safety);
            return (
              <View key={order.id} style={styles.itemCard}>
                <View style={styles.rowBetween}>
                  <Text style={styles.statusText}>{supplementStatusLabel(order.status)}</Text>
                  <Text style={styles.itemTitle}>{order.name}</Text>
                </View>
                <Text style={styles.bodyText}>
                  {order.dose_amount ?? "—"} {order.dose_unit ?? ""} · {order.frequency ?? "دفعات ثبت نشده"}
                </Text>
                {order.duration_days !== null ? <Text style={styles.mutedText}>مدت: {formatNutritionNumber(order.duration_days)} روز</Text> : null}
                {order.instructions ? <Text style={styles.bodyText}>دستور مصرف: {order.instructions}</Text> : null}
                {order.rationale ? <Text style={styles.mutedText}>علت ثبت: {order.rationale}</Text> : null}
                {safety.blocked ? <Notice message={safety.message} title={safety.title} variant="danger" /> : <Notice message={safety.message} title={safety.title} variant="success" />}
                <DisclosureCard
                  icon="nutrition"
                  summary="جزئیات علمی برای مرور دقیق‌تر"
                  title="سهم تغذیه و کنترل مواجهه"
                >
                  <Text style={styles.mutedText}>سهم مکمل</Text>
                  <ContributionRows values={order.supplement_nutrient_contribution} />
                  <Text style={styles.mutedText}>
                    کنترل مواجهه ترکیبی: {order.combined_exposure_safety.hard_blocks.length > 0 ? "نیازمند بررسی" : "بدون منع ثبت‌شده"}
                  </Text>
                </DisclosureCard>
                {!safety.blocked && !order.acknowledged_at ? (
                  <Button label="دستور را دیدم" onPress={() => onAcknowledge(order)} />
                ) : null}
                {order.acknowledged_at ? <Text style={styles.statusText}>تأیید عضو ثبت شده است.</Text> : null}
              </View>
            );
          })}
        </View>
      )}
    </Card>
  );
}

const contributionLabels: Readonly<Record<string, string>> = {
  carbohydrate_g: "کربوهیدرات",
  energy_kcal: "انرژی",
  fat_g: "چربی",
  protein_g: "پروتئین",
};

function ContributionRows({ values }: { readonly values: Readonly<Record<string, string>> }) {
  const rows = Object.entries(values);
  if (rows.length === 0) return <Text style={styles.mutedText}>—</Text>;
  return (
    <View style={styles.contributionStack}>
      {rows.map(([code, value]) => (
        <View key={code} style={styles.contributionRow}>
          <Text style={styles.summaryValue}>{value}</Text>
          <Text style={styles.summaryLabel}>{contributionLabels[code] ?? "سایر مواد مغذی"}</Text>
        </View>
      ))}
    </View>
  );
}

function VerifiedSupplementCatalogue({
  items,
  state,
}: {
  readonly items: readonly NutritionSupplementCatalogue[];
  readonly state: ReturnType<typeof getMobileViewState<NutritionSupplementCatalogue[]>>;
}) {
  const verified = items.filter((item) => item.verification_status === "verified");
  if (verified.length === 0) return null;
  return (
    <Card style={styles.card}>
      <Text style={styles.cardTitle}>فهرست مکمل‌های تأییدشده</Text>
      {state.status === "offline" || state.status === "stale" ? <Notice message="آخرین فهرست تأییدشده نمایش داده می‌شود." variant="offline" /> : null}
      <View style={styles.catalogueStack}>
        {verified.map((item) => (
          <View key={item.id} style={styles.catalogueItem}>
            <Text style={styles.itemTitle}>{item.name_fa}</Text>
            <Text style={styles.mutedText}>{item.name_en}</Text>
          </View>
        ))}
      </View>
    </Card>
  );
}

function stateData<TData>(state: ReturnType<typeof getMobileViewState<TData>>): TData | undefined {
  if (state.status === "loading") return undefined;
  return "data" in state ? state.data : undefined;
}

function optionalText(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function labFilenameForMimeType(mimeType: "image/jpeg" | "image/png"): string {
  return mimeType === "image/png" ? "lab-image.png" : "lab-image.jpg";
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${formatNutritionNumber(bytes)} بایت`;
  if (bytes < 1024 * 1024) return `${formatNutritionNumber(Math.round(bytes / 1024))} کیلوبایت`;
  return `${formatNutritionNumber(Math.round(bytes / (1024 * 1024)))} مگابایت`;
}

function clinicalErrorMessage(error: unknown, fallback = "عملیات پرونده سلامت انجام نشد؛ دوباره تلاش کن."): string {
  if (error instanceof ApiError && error.message !== "Request failed") return error.message;
  if (error instanceof Error && /offline|connection|network/i.test(error.message)) {
    return "اتصال اینترنت در دسترس نیست؛ بعداً دوباره تلاش کن.";
  }
  if (error instanceof Error && /format|size|pixel|orientation|PDF|document/i.test(error.message)) {
    return error.message;
  }
  return fallback;
}

function useConnectivityStatus(): ConnectivityStatus {
  const [status, setStatus] = useState<ConnectivityStatus>(connectivityMonitor.getSnapshot().status);
  useEffect(() => connectivityMonitor.subscribe((snapshot) => setStatus(snapshot.status)), []);
  return status;
}

const styles = StyleSheet.create({
  actions: {
    flexDirection: "row-reverse",
    flexWrap: "wrap",
    gap: fiticianTokens.spacing[2],
  },
  bodyText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    lineHeight: 23,
    textAlign: "right",
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
    textAlign: "right",
    writingDirection: "rtl",
  },
  catalogueItem: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[1],
    padding: fiticianTokens.spacing[3],
  },
  catalogueStack: {
    gap: fiticianTokens.spacing[2],
  },
  contributionRow: {
    alignItems: "center",
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.small,
    borderWidth: 1,
    flexDirection: "row-reverse",
    justifyContent: "space-between",
    padding: fiticianTokens.spacing[3],
  },
  contributionStack: {
    gap: fiticianTokens.spacing[2],
  },
  count: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.sm,
    writingDirection: "ltr",
  },
  fileName: {
    color: fiticianTokens.colors.aqua,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "right",
    writingDirection: "rtl",
  },
  formStack: {
    gap: fiticianTokens.spacing[3],
  },
  headingCopy: {
    alignItems: "flex-end",
    flex: 1,
    gap: fiticianTokens.spacing[1],
  },
  itemCard: {
    backgroundColor: fiticianTokens.colors.surfaceSubtle,
    borderColor: fiticianTokens.colors.line,
    borderRadius: fiticianTokens.radii.medium,
    borderWidth: 1,
    gap: fiticianTokens.spacing[2],
    padding: fiticianTokens.spacing[3],
  },
  itemStack: {
    gap: fiticianTokens.spacing[3],
  },
  itemTitle: {
    color: fiticianTokens.colors.ink,
    flexShrink: 1,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "right",
    writingDirection: "rtl",
  },
  metaStack: {
    gap: fiticianTokens.spacing[1],
  },
  multiline: {
    minHeight: 90,
    textAlignVertical: "top",
  },
  mutedText: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    lineHeight: 20,
    textAlign: "right",
    writingDirection: "rtl",
  },
  rowBetween: {
    alignItems: "flex-start",
    flexDirection: "row-reverse",
    gap: fiticianTokens.spacing[3],
    justifyContent: "space-between",
  },
  section: {
    gap: fiticianTokens.spacing[3],
  },
  statusText: {
    color: fiticianTokens.colors.success,
    flexShrink: 0,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.xs,
    textAlign: "left",
    writingDirection: "rtl",
  },
  summaryLabel: {
    color: fiticianTokens.colors.muted,
    fontFamily: fiticianTokens.typography.fontFamily.bodyPersian,
    fontSize: fiticianTokens.typography.fontSize.sm,
    textAlign: "right",
    writingDirection: "rtl",
  },
  summaryValue: {
    color: fiticianTokens.colors.ink,
    fontFamily: fiticianTokens.typography.fontFamily.bodyEnglish,
    fontSize: fiticianTokens.typography.fontSize.body,
    fontWeight: fiticianTokens.typography.fontWeight.bold,
    textAlign: "left",
    writingDirection: "ltr",
  },
});
