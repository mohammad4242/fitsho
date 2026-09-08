import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { LanguageSwitcher } from "../../shared/LanguageSwitcher";

export function PublicPageFrame({ children }: { children: ReactNode }) {
  const { i18n, t } = useTranslation();
  const english = i18n.resolvedLanguage === "en";
  const l = (fa: string, en: string) => english ? en : fa;

  return (
    <main className="public-account-page fitsho-page" dir={english ? "ltr" : "rtl"}>
      <div className="public-account-page__container">
        <header className="public-account-page__header">
          <Link className="brand-mark brand-mark--dark" to="/">
            <span className="brand-mark__pulse" aria-hidden="true" />
            {t("common.brand")}
          </Link>
          <LanguageSwitcher />
        </header>
        {children}
        <footer className="public-account-page__footer">
          <Link to="/delete-account">{l("حذف حساب", "Delete account")}</Link>
          <Link to="/privacy">{l("سیاست حریم خصوصی", "Privacy policy")}</Link>
        </footer>
      </div>
    </main>
  );
}
