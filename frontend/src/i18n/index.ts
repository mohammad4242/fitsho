import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "./en";
import fa from "./fa";

const STORAGE_KEY = "fitsho-language";
const storedLanguage =
  typeof window === "undefined" ? null : window.localStorage.getItem(STORAGE_KEY);
const initialLanguage = storedLanguage === "en" ? "en" : "fa";

function applyDocumentLanguage(language: string) {
  const normalized = language.startsWith("en") ? "en" : "fa";
  if (typeof document !== "undefined") {
    document.documentElement.lang = normalized;
    document.documentElement.dir = normalized === "fa" ? "rtl" : "ltr";
  }
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, normalized);
  }
}

void i18n.use(initReactI18next).init({
  resources: { en, fa },
  lng: initialLanguage,
  fallbackLng: "fa",
  interpolation: { escapeValue: false },
});

applyDocumentLanguage(initialLanguage);
i18n.on("languageChanged", applyDocumentLanguage);

export default i18n;
