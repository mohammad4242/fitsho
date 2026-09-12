import { useTranslation } from "react-i18next";
import { useRegisterSW } from "virtual:pwa-register/react";

export function PwaUpdatePrompt() {
  const { i18n } = useTranslation();
  const { needRefresh: [needRefresh, setNeedRefresh], updateServiceWorker } = useRegisterSW();
  const english = i18n.resolvedLanguage === "en";
  const l = (fa: string, en: string) => english ? en : fa;

  if (!needRefresh) return null;

  return (
    <aside className="pwa-update-prompt" role="status" aria-live="polite">
      <div>
        <strong>{l("نسخه جدید فیتیشن آماده است", "A new version of Fitician is available")}</strong>
        <span>{l("هر زمان آماده بودی، به‌روزرسانی کن.", "Update when you are ready.")}</span>
      </div>
      <div className="pwa-update-prompt__actions">
        <button className="fitsho-button" type="button" onClick={() => void updateServiceWorker(true)}>
          {l("به‌روزرسانی", "Update")}
        </button>
        <button className="fitsho-button-secondary" type="button" onClick={() => setNeedRefresh(false)}>
          {l("بعداً", "Later")}
        </button>
      </div>
    </aside>
  );
}
