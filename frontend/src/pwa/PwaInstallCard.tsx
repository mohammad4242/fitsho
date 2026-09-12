import { useState } from "react";
import { useTranslation } from "react-i18next";

import { usePwaInstall } from "./usePwaInstall";

export function PwaInstallCard() {
  const { i18n } = useTranslation();
  const { state, canPrompt, install } = usePwaInstall();
  const [dismissed, setDismissed] = useState(false);
  const english = i18n.resolvedLanguage === "en";
  const l = (fa: string, en: string) => english ? en : fa;

  if (dismissed || state === "installed" || state === "unsupported") return null;
  if (state === "chromium" && !canPrompt) return null;

  return (
    <section className="pwa-install-card" aria-label={l("نصب فیتیشن", "Install Fitician")}>
      <div>
        <p>{l("فیتیشن روی دستگاه شما", "Fitician on your device")}</p>
        <h2>{l("دسترسی سریع‌تر به فیتیشن", "Faster access to Fitician")}</h2>
        {state === "ios-instructions" ? (
          <ol>
            <li>{l("در Safari یا مرورگر، دکمه اشتراک‌گذاری را بزنید.", "In Safari or your browser, open Share.")}</li>
            <li>{l("«افزودن به صفحهٔ اصلی» را انتخاب کنید.", "Choose Add to Home Screen.")}</li>
            <li>{l("«Open as Web App» را روشن و «افزودن» را بزنید.", "Enable Open as Web App, then tap Add.")}</li>
          </ol>
        ) : <p>{l("برای نصب امن و سریع، از دکمه نصب مرورگر استفاده کن.", "Use the browser install prompt for fast, secure access.")}</p>}
      </div>
      <div className="pwa-install-card__actions">
        {state === "chromium" && (
          <button className="fitsho-button" type="button" onClick={() => void install()}>
            {l("نصب", "Install")}
          </button>
        )}
        <button className="fitsho-button-secondary" type="button" onClick={() => setDismissed(true)}>
          {l("بعداً", "Later")}
        </button>
      </div>
    </section>
  );
}
