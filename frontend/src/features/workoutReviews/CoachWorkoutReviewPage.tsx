import { useTranslation } from "react-i18next";

export function CoachWorkoutReviewPage() {
  const { i18n } = useTranslation();
  const fa = i18n.resolvedLanguage !== "en";

  return (
    <main dir={fa ? "rtl" : "ltr"}>
      <h1>{fa ? "بازبینی برنامه‌های تمرینی" : "Workout plan reviews"}</h1>
    </main>
  );
}
