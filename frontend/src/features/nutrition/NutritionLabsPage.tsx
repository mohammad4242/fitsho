import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import * as api from "./api";
import "./nutritionEstimate.css";

type Lab = Awaited<ReturnType<typeof api.listLabDocuments>>[number];
type IconName =
  | "arrow-back"
  | "calendar"
  | "check"
  | "clock"
  | "file"
  | "flask"
  | "lab"
  | "note"
  | "plus"
  | "shield"
  | "tag"
  | "trash"
  | "upload"
  | "eye";

function LabIcon({ name, size = 20 }: { name: IconName; size?: number }) {
  const iconProps = {
    fill: "none",
    stroke: "currentColor",
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    strokeWidth: 1.8,
  };

  const paths: Record<IconName, ReactNode> = {
    "arrow-back": <path {...iconProps} d="M19 12H5m6-6-6 6 6 6" />,
    calendar: <><rect {...iconProps} height="16" rx="2.5" width="17" x="3.5" y="5" /><path {...iconProps} d="M7 3v4M17 3v4M3.5 10h17M8 14h2m2 0h2m-6 3h2m2 0h2" /></>,
    check: <><path {...iconProps} d="m5 12 4.2 4.2L19 6.5" /><circle {...iconProps} cx="12" cy="12" r="9" /></>,
    clock: <><circle {...iconProps} cx="12" cy="12" r="8.5" /><path {...iconProps} d="M12 7v5l3.5 2" /></>,
    file: <><path {...iconProps} d="M7 3.5h6l4 4V20a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1Z" /><path {...iconProps} d="M13 3.5V8h4M9 12h6m-6 3h6" /></>,
    flask: <><path {...iconProps} d="M9 3h6m-5 0v5.4L5 19a1.4 1.4 0 0 0 1.2 2h11.6a1.4 1.4 0 0 0 1.2-2L14 8.4V3" /><path {...iconProps} d="M7.2 16h9.6M9 13.2h6" /></>,
    lab: <><path {...iconProps} d="M4 21h16M6 21v-4.5L9 13V4h6v9l3 3.5V21M8 4h8M9 8h6" /></>,
    note: <><path {...iconProps} d="M5 3.5h14v17H5zM8 7h8M8 11h8M8 15h5" /></>,
    plus: <path {...iconProps} d="M12 5v14M5 12h14" />,
    shield: <><path {...iconProps} d="M12 3.5 19 6v5.2c0 4.3-2.8 7.8-7 9.3-4.2-1.5-7-5-7-9.3V6l7-2.5Z" /><path {...iconProps} d="m9 12 2 2 4-4" /></>,
    tag: <><path {...iconProps} d="M4 5.5v5.2l8.8 8.8a1.7 1.7 0 0 0 2.4 0l4.3-4.3a1.7 1.7 0 0 0 0-2.4L10.7 4H5.5A1.5 1.5 0 0 0 4 5.5Z" /><circle {...iconProps} cx="8" cy="8" r="1" /></>,
    trash: <><path {...iconProps} d="M4.5 7h15M10 11v5m4-5v5M8 7l.7 13h6.6L16 7M9 7V4h6v3" /></>,
    upload: <><path {...iconProps} d="M12 15V4m0 0L8 8m4-4 4 4M5 13v5.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V13" /></>,
    eye: <><path {...iconProps} d="M2.8 12s3.3-5 9.2-5 9.2 5 9.2 5-3.3 5-9.2 5-9.2-5-9.2-5Z" /><circle {...iconProps} cx="12" cy="12" r="2.2" /></>,
  };

  return <svg aria-hidden="true" height={size} viewBox="0 0 24 24" width={size}>{paths[name]}</svg>;
}

function fileKind(contentType: string, l: (persian: string, english: string) => string) {
  return contentType === "application/pdf" ? l("PDF", "PDF") : l("تصویر", "Image");
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  const megabytes = bytes / (1024 * 1024);
  if (megabytes >= 1) return `${megabytes.toFixed(1)} MB`;
  return `${Math.round(bytes / 1024)} KB`;
}

function reviewStatus(status: string, l: (persian: string, english: string) => string) {
  switch (status) {
    case "approved":
      return { label: l("تأییدشده", "Approved"), icon: "check" as const, tone: "approved" };
    case "under_review":
      return { label: l("در حال بررسی", "Under review"), icon: "clock" as const, tone: "review" };
    case "rejected":
      return { label: l("نیازمند اصلاح", "Needs attention"), icon: "clock" as const, tone: "attention" };
    default:
      return { label: l("بارگذاری‌شده", "Uploaded"), icon: "check" as const, tone: "uploaded" };
  }
}

function requestStatus(status: string, l: (persian: string, english: string) => string) {
  if (status === "requested") return l("درخواست‌شده", "Requested");
  if (status === "fulfilled") return l("تکمیل‌شده", "Fulfilled");
  return status;
}

export function NutritionLabsPage() {
  const { i18n } = useTranslation();
  const fa = i18n.language === "fa";
  const l = (persian: string, english: string) => fa ? persian : english;
  const navigate = useNavigate();
  const [labs, setLabs] = useState<Lab[]>([]);
  const [requests, setRequests] = useState<Awaited<ReturnType<typeof api.listLabRequests>>>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [testDate, setTestDate] = useState("");
  const [laboratoryName, setLaboratoryName] = useState("");
  const [category, setCategory] = useState("");
  const [note, setNote] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const load = () => Promise.all([api.listLabDocuments(), api.listLabRequests()])
    .then(([documents, requested]) => {
      setLabs(documents);
      setRequests(requested);
      setError(false);
    })
    .catch(() => setError(true))
    .finally(() => setLoading(false));

  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function upload(file: File | undefined) {
    if (!file) return;
    setSelectedFile(file);
    setBusy(true);
    try {
      await api.uploadLabDocument(file, {
        requestId: requests.find((request) => request.status === "requested")?.id,
        testDate: testDate || undefined,
        laboratoryName: laboratoryName || undefined,
        userNote: note || undefined,
        category: category || undefined,
      });
      await load();
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  async function openLab(lab: Lab) {
    const grant = await api.grantLabDocumentAccess(lab.id);
    window.open(grant.access_url, "_blank", "noopener,noreferrer");
  }

  async function removeLab(documentId: string) {
    setBusy(true);
    try {
      await api.deleteLabDocument(documentId);
      await load();
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  return <main className="nutrition-estimate-page nutrition-labs-page" dir={fa ? "rtl" : "ltr"}>
    <section className="nutrition-estimate-hero nutrition-labs-hero">
      <div className="nutrition-labs-hero__topline">
        <button className="secondary-button nutrition-labs-back" type="button" onClick={() => navigate(-1)}>
          <LabIcon name="arrow-back" size={17} />
          <span>{l("بازگشت", "Back")}</span>
        </button>
        <span className="nutrition-labs-privacy"><LabIcon name="shield" size={16} />{l("خصوصی و امن", "Private & secure")}</span>
      </div>
      <div className="nutrition-labs-hero__content">
        <div>
          <p className="nutrition-eyebrow"><LabIcon name="flask" size={15} />{l("پرونده سلامت", "Health record")}</p>
          <h1 className="fitsho-display"><span className="nutrition-labs-title-icon"><LabIcon name="flask" size={28} /></span>{l("آزمایش‌های من", "My labs")}</h1>
          <p>{l("نتایج آزمایش‌هایت را یک‌جا نگه دار تا خودت و پزشک مسئول، تصویر کامل‌تری از سلامتت داشته باشید.", "Keep your lab results in one place so you and your assigned physician have a clearer view of your health.")}</p>
        </div>
        <div className="nutrition-labs-hero__count"><strong>{labs.length.toLocaleString(fa ? "fa-IR" : "en-US")}</strong><span>{l("فایل ثبت‌شده", "saved files")}</span></div>
      </div>
    </section>

    {loading && <p role="status" className="nutrition-labs-state">{l("در حال دریافت آزمایش‌ها…", "Loading lab documents…")}</p>}
    {error && <p role="alert" className="nutrition-labs-alert">{l("عملیات آزمایش انجام نشد.", "The lab operation failed.")}</p>}

    <div className="nutrition-labs-layout">
      <section className="nutrition-labs-card nutrition-labs-form" aria-labelledby="nutrition-labs-form-title">
        <header className="nutrition-labs-card__header">
          <span className="nutrition-labs-card__icon"><LabIcon name="plus" size={21} /></span>
          <div><p className="nutrition-eyebrow">{l("ثبت جدید", "New record")}</p><h2 id="nutrition-labs-form-title">{l("افزودن آزمایش", "Add lab result")}</h2></div>
        </header>
        <div className="nutrition-labs-form__fields">
          <label className="nutrition-labs-field">
            <span className="nutrition-labs-field__label"><span className="nutrition-labs-field__icon"><LabIcon name="calendar" size={17} /></span>{l("تاریخ آزمایش", "Test date")}</span>
            <input type="date" value={testDate} onChange={(event) => setTestDate(event.target.value)} />
          </label>
          <label className="nutrition-labs-field">
            <span className="nutrition-labs-field__label"><span className="nutrition-labs-field__icon"><LabIcon name="lab" size={17} /></span>{l("نام آزمایشگاه", "Laboratory name")}</span>
            <input value={laboratoryName} onChange={(event) => setLaboratoryName(event.target.value)} />
          </label>
          <label className="nutrition-labs-field">
            <span className="nutrition-labs-field__label"><span className="nutrition-labs-field__icon"><LabIcon name="tag" size={17} /></span>{l("دسته‌بندی", "Category")}</span>
            <input value={category} onChange={(event) => setCategory(event.target.value)} />
          </label>
          <label className="nutrition-labs-field nutrition-labs-field--full">
            <span className="nutrition-labs-field__label"><span className="nutrition-labs-field__icon"><LabIcon name="note" size={17} /></span>{l("یادداشت", "Note")}</span>
            <textarea rows={3} value={note} onChange={(event) => setNote(event.target.value)} />
          </label>
          <div className="nutrition-labs-upload nutrition-labs-field--full">
            <span className="nutrition-labs-field__label"><span className="nutrition-labs-field__icon"><LabIcon name="upload" size={17} /></span>{l("فایل آزمایش", "Lab file")}</span>
            <div className="nutrition-labs-upload__row">
              <label className="nutrition-labs-upload__button" htmlFor="nutrition-labs-file">
                <LabIcon name="upload" size={18} />
                <span>{selectedFile ? l("تغییر فایل", "Change file") : l("انتخاب فایل", "Choose file")}</span>
                <input id="nutrition-labs-file" aria-label={l("انتخاب فایل آزمایش", "Choose lab file")} accept="application/pdf,image/jpeg,image/png" disabled={busy} type="file" onChange={(event) => void upload(event.target.files?.[0])} />
              </label>
              <div className={`nutrition-labs-upload__filename${selectedFile ? " has-file" : ""}`} aria-live="polite">
                <LabIcon name="file" size={19} />
                <span>{selectedFile?.name ?? l("هنوز فایلی انتخاب نشده", "No file selected")}</span>
              </div>
            </div>
            <small>{l("PDF یا تصویر PNG/JPG تا سقف مجاز برنامه", "PDF or PNG/JPG image within the allowed size")}</small>
          </div>
        </div>
      </section>

      <section className="nutrition-labs-card nutrition-labs-requests" aria-labelledby="nutrition-labs-requests-title">
        <header className="nutrition-labs-card__header">
          <span className="nutrition-labs-card__icon nutrition-labs-card__icon--soft"><LabIcon name="clock" size={21} /></span>
          <div><p className="nutrition-eyebrow">{l("همراهی پزشک", "Physician care")}</p><h2 id="nutrition-labs-requests-title">{l("درخواست‌های پزشک", "Physician requests")}</h2></div>
        </header>
        {requests.length === 0 ? <p className="nutrition-labs-requests__empty">{l("درخواستی ثبت نشده است.", "No request has been recorded.")}</p> : <div className="nutrition-labs-requests__list">{requests.map((request) => <article key={request.id}>
          <div><strong>{request.requested_tests.join("، ")}</strong><span>{requestStatus(request.status, l)}</span></div>
          {request.user_visible_reason && <p>{request.user_visible_reason}</p>}
        </article>)}</div>}
      </section>
    </div>

    {!loading && labs.length === 0 && <section className="nutrition-labs-empty" aria-labelledby="nutrition-labs-empty-title">
      <span className="nutrition-labs-empty__icon"><LabIcon name="file" size={30} /></span>
      <div><p className="nutrition-eyebrow">{l("شروع پرونده", "Start your record")}</p><h2 id="nutrition-labs-empty-title">{l("هنوز آزمایشی ثبت نشده", "No lab results yet")}</h2><p>{l("اولین فایل آزمایش را از فرم بالا اضافه کن تا سابقه سلامتت همیشه مرتب و در دسترس باشد.", "Add your first lab file above to keep your health history organized and easy to access.")}</p></div>
    </section>}

    {labs.length > 0 && <section className="nutrition-labs-history" aria-labelledby="nutrition-labs-history-title">
      <div className="nutrition-labs-section-heading"><div><p className="nutrition-eyebrow">{l("سوابق ذخیره‌شده", "Saved history")}</p><h2 id="nutrition-labs-history-title">{l("آزمایش‌های ثبت‌شده", "Lab history")}</h2></div><span>{labs.length.toLocaleString(fa ? "fa-IR" : "en-US")} {l("فایل", "files")}</span></div>
      <div className="nutrition-labs-list">{labs.map((lab) => {
        const status = reviewStatus(lab.review_status, l);
        return <article className="nutrition-labs-item" key={lab.id}>
          <div className="nutrition-labs-item__top">
            <span className="nutrition-labs-item__file-icon"><LabIcon name="file" size={22} /></span>
            <div className="nutrition-labs-item__title"><h3>{lab.original_filename}</h3><span>{fileKind(lab.content_type, l)} · {formatFileSize(lab.byte_size)}</span></div>
            <span className={`nutrition-labs-status nutrition-labs-status--${status.tone}`}><LabIcon name={status.icon} size={15} />{status.label}</span>
          </div>
          <dl className="nutrition-labs-item__meta">
            <div><dt><LabIcon name="calendar" size={15} />{l("تاریخ", "Date")}</dt><dd>{lab.test_date ?? l("نامشخص", "Not provided")}</dd></div>
            <div><dt><LabIcon name="lab" size={15} />{l("آزمایشگاه", "Laboratory")}</dt><dd>{lab.laboratory_name ?? l("نامشخص", "Not provided")}</dd></div>
            <div><dt><LabIcon name="tag" size={15} />{l("دسته‌بندی", "Category")}</dt><dd>{lab.category ?? l("بدون دسته‌بندی", "Uncategorized")}</dd></div>
          </dl>
          {(lab.user_note || lab.review_notes) && <div className="nutrition-labs-item__note"><LabIcon name="note" size={16} /><p>{lab.user_note ?? lab.review_notes}</p></div>}
          <div className="nutrition-labs-item__actions">
            <button className="nutrition-labs-item__open" onClick={() => void openLab(lab)} type="button"><LabIcon name="eye" size={17} />{l("مشاهده فایل", "Open file")}</button>
            <button className="nutrition-labs-item__delete" disabled={busy} onClick={() => void removeLab(lab.id)} type="button"><LabIcon name="trash" size={17} />{l("حذف", "Delete")}</button>
          </div>
        </article>;
      })}</div>
    </section>}
  </main>;
}
