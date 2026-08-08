import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import * as api from "./api";
import "./nutritionEstimate.css";

type Lab = Awaited<ReturnType<typeof api.listLabDocuments>>[number];

export function NutritionLabsPage() {
  const { i18n } = useTranslation();
  const fa = i18n.language === "fa";
  const l = (persian: string, english: string) => fa ? persian : english;
  const [labs, setLabs] = useState<Lab[]>([]);
  const [busy, setBusy] = useState(false);
  const load = () => api.listLabDocuments().then(setLabs);
  useEffect(() => { void load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  async function upload(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    try { await api.uploadLabDocument(file); await load(); } finally { setBusy(false); }
  }
  return <main className="nutrition-estimate-page" dir={fa ? "rtl" : "ltr"}>
    <section className="nutrition-estimate-hero"><h1>{l("آزمایش‌های من", "My lab documents")}</h1><p>{l("آپلود برای همه اختیاری است؛ فقط خودت و پزشک مسئول به فایل دسترسی دارید.", "Uploads are optional. Only you and the assigned physician can access them.")}</p></section>
    <section className="nutrition-estimate-notes"><input disabled={busy} type="file" accept="application/pdf,image/jpeg,image/png" onChange={(event) => void upload(event.target.files?.[0])} /></section>
    <section className="nutrition-target-grid">{labs.map((lab) => <a className="nutrition-target-card" href={`/api/v1/nutrition/labs/${lab.id}/file`} key={lab.id}><strong>{lab.original_filename}</strong><small>{lab.review_status}</small></a>)}</section>
  </main>;
}
