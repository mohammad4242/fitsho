import { useTranslation } from "react-i18next";

import { AuthShell } from "../../shared/AuthShell";

export function OnboardingPage() {
  const { t } = useTranslation();

  return (
    <AuthShell>
      <div className="form-heading">
        <p className="eyebrow eyebrow--accent">{t("onboarding.eyebrow")}</p>
        <h2>{t("onboarding.title")}</h2>
        <p>{t("onboarding.intro")}</p>
      </div>
    </AuthShell>
  );
}
