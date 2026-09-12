import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useRegisterSW } from "virtual:pwa-register/react";

export function PwaUpdatePrompt() {
  const { i18n } = useTranslation();
  const { needRefresh: [needRefresh], updateServiceWorker } = useRegisterSW();
  const [dismissedForCurrentSession, setDismissedForCurrentSession] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const english = i18n.resolvedLanguage === "en";
  const l = (fa: string, en: string) => english ? en : fa;

  useEffect(() => {
    if (!needRefresh) {
      setDismissedForCurrentSession(false);
      setIsUpdating(false);
    }
  }, [needRefresh]);

  async function handleUpdate() {
    if (isUpdating) return;

    setIsUpdating(true);
    try {
      await updateServiceWorker(true);
    } catch {
      setIsUpdating(false);
    }
  }

  if (!needRefresh || dismissedForCurrentSession) return null;

  return (
    <aside
      className="pwa-update-prompt"
      role="dialog"
      aria-modal="false"
      aria-live="polite"
      aria-labelledby="pwa-update-title"
      aria-describedby="pwa-update-description"
    >
      <div>
        <strong id="pwa-update-title">{l("نسخه جدید فیتیشن آماده است", "A new version of Fitician is available")}</strong>
        <span id="pwa-update-description">{l("هر زمان آماده بودی، به‌روزرسانی کن.", "Update when you are ready.")}</span>
      </div>
      <div className="pwa-update-prompt__actions">
        <button
          className="fitsho-button"
          type="button"
          disabled={isUpdating}
          onClick={() => void handleUpdate()}
        >
          {isUpdating ? l("در حال به‌روزرسانی…", "Updating…") : l("به‌روزرسانی", "Update")}
        </button>
        <button
          className="fitsho-button-secondary"
          type="button"
          disabled={isUpdating}
          onClick={() => setDismissedForCurrentSession(true)}
        >
          {l("بعداً", "Later")}
        </button>
      </div>
    </aside>
  );
}
