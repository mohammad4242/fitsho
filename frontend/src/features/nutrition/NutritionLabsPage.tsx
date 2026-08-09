import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import * as api from "./api";
import "./nutritionEstimate.css";

type Lab = Awaited<ReturnType<typeof api.listLabDocuments>>[number];

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
  const load = () => Promise.all([api.listLabDocuments(), api.listLabRequests()]).then(([documents, requested]) => { setLabs(documents); setRequests(requested); setError(false); }).catch(() => setError(true)).finally(() => setLoading(false));
  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  async function upload(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    try { await api.uploadLabDocument(file, { requestId: requests.find((request) => request.status === "requested")?.id, testDate: testDate || undefined, laboratoryName: laboratoryName || undefined, userNote: note || undefined, category: category || undefined }); await load(); }
    catch { setError(true); }
    finally { setBusy(false); }
  }
  async function openLab(lab: Lab) {
    const grant = await api.grantLabDocumentAccess(lab.id);
    window.open(grant.access_url, "_blank", "noopener,noreferrer");
  }
  return <main className="nutrition-estimate-page" dir={fa ? "rtl" : "ltr"}>
    <section className="nutrition-estimate-hero"><button className="secondary-button" type="button" onClick={() => navigate(-1)}>{l("بازگشت", "Back")}</button><h1>{l("آزمایش‌های من", "My lab documents")}</h1><p>{l("آپلود برای همه اختیاری است؛ فقط خودت و پزشک مسئول به فایل دسترسی دارید.", "Uploads are optional. Only you and the assigned physician can access them.")}</p></section>
    {loading && <p role="status">{l("در حال دریافت آزمایش‌ها…", "Loading lab documents…")}</p>}
    {error && <p role="alert">{l("عملیات آزمایش انجام نشد.", "The lab operation failed.")}</p>}
    <section className="nutrition-estimate-notes"><h2>{l("افزودن آزمایش", "Add lab document")}</h2><label>{l("تاریخ آزمایش", "Test date")}<input type="date" value={testDate} onChange={(event) => setTestDate(event.target.value)} /></label><label>{l("نام آزمایشگاه", "Laboratory name")}<input value={laboratoryName} onChange={(event) => setLaboratoryName(event.target.value)} /></label><label>{l("دسته‌بندی", "Category")}<input value={category} onChange={(event) => setCategory(event.target.value)} /></label><label>{l("یادداشت", "Note")}<textarea value={note} onChange={(event) => setNote(event.target.value)} /></label><input aria-label={l("انتخاب فایل آزمایش", "Choose lab file")} disabled={busy} type="file" accept="application/pdf,image/jpeg,image/png" onChange={(event) => void upload(event.target.files?.[0])} /></section>
    <section className="nutrition-estimate-notes"><h2>{l("درخواست‌های پزشک", "Physician requests")}</h2>{requests.length === 0 ? <p>{l("درخواستی ثبت نشده است.", "No request has been recorded.")}</p> : requests.map((request) => <article key={request.id}><strong>{request.requested_tests.join("، ")}</strong><p>{request.user_visible_reason}</p><small>{request.status}</small></article>)}</section>
    {!loading && labs.length === 0 && <p className="nutrition-estimate-state">{l("هنوز آزمایشی بارگذاری نشده است.", "No lab document has been uploaded yet.")}</p>}
    <section className="nutrition-target-grid">{labs.map((lab) => <article className="nutrition-target-card" key={lab.id}><strong>{lab.original_filename}</strong><small>{lab.test_date ?? l("تاریخ نامشخص", "No date")} · {lab.laboratory_name ?? l("آزمایشگاه نامشخص", "Unknown lab")}</small><small>{lab.review_status}</small>{lab.review_notes && <p>{lab.review_notes}</p>}<button onClick={() => void openLab(lab)} type="button">{l("مشاهده", "Open")}</button><button disabled={busy} onClick={() => { setBusy(true); void api.deleteLabDocument(lab.id).then(load).catch(() => setError(true)).finally(() => setBusy(false)); }} type="button">{l("حذف", "Delete")}</button></article>)}</section>
  </main>;
}
