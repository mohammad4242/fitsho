import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { LanguageSwitcher } from "./LanguageSwitcher";

type AuthShellProps = {
  children: ReactNode;
};

export function AuthShell({ children }: AuthShellProps) {
  const { t } = useTranslation();

  return (
    <main className="auth-shell fitsho-page">
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
