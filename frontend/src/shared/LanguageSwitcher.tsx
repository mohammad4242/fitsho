import { useTranslation } from "react-i18next";

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation();
  const isPersian = i18n.resolvedLanguage !== "en";
  const label = isPersian
    ? t("common.switchToEnglish")
    : t("common.switchToPersian");

  return (
    <button
      className="language-switcher"
      type="button"
      onClick={() => void i18n.changeLanguage(isPersian ? "en" : "fa")}
      aria-label={label}
    >
      <span aria-hidden="true">◎</span>
      {label}
    </button>
  );
}
