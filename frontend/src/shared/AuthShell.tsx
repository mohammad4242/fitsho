import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { LanguageSwitcher } from "./LanguageSwitcher";

type AuthShellProps = {
  children: ReactNode;
};

export function AuthShell({ children }: AuthShellProps) {
  const { t } = useTranslation();

  return (
    <main className="auth-shell">
      <section className="brand-panel" aria-labelledby="fitsho-promise">
        <div className="brand-panel__top">
          <a className="brand-mark" href="/" aria-label={t("common.brand")}>
            <span className="brand-mark__pulse" aria-hidden="true" />
            {t("common.brand")}
          </a>
          <LanguageSwitcher />
        </div>

        <div className="brand-copy">
          <p className="eyebrow">{t("brandPanel.eyebrow")}</p>
          <h1 id="fitsho-promise" className="fitsho-display">{t("brandPanel.title")}</h1>
          <p>{t("brandPanel.body")}</p>
        </div>

        <div className="coach-note" aria-hidden="true">
          <div className="coach-note__heading">
            <span>{t("brandPanel.prescription")}</span>
            <span>{t("brandPanel.today")}</span>
          </div>
          <div className="coach-note__path">
            <span />
            <span />
            <span />
          </div>
          <div className="coach-note__labels">
            <span>{t("brandPanel.focus")}</span>
            <span>{t("brandPanel.adaptive")}</span>
            <span>{t("brandPanel.progress")}</span>
          </div>
        </div>
      </section>

      <section className="form-panel">
        <div className="form-panel__mobile-nav">
          <a className="brand-mark brand-mark--dark" href="/">
            <span className="brand-mark__pulse" aria-hidden="true" />
            {t("common.brand")}
          </a>
          <LanguageSwitcher />
        </div>
        <div className="form-wrap">{children}</div>
      </section>
    </main>
  );
}
