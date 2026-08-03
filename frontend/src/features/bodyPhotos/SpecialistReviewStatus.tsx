import { useTranslation } from "react-i18next";

import type { SpecialistReviewState } from "./types";

export function SpecialistReviewStatus({ review }: { review: SpecialistReviewState }) {
  const { t } = useTranslation();
  const state = review.decision ?? "pending";
  const approved = review.decision === "approved";

  return (
    <div
      className={`body-analysis-review body-analysis-review--${state}`}
      aria-label={t("bodyPhotos.results.reviewAria", {
        role: t(`bodyPhotos.results.reviewRoles.${review.role}`),
        state: t(`bodyPhotos.results.reviewStates.${state}`),
      })}
    >
      <span aria-hidden="true">{approved ? "✓" : state === "pending" ? "○" : "!"}</span>
      <div>
        <strong>{t(`bodyPhotos.results.reviewRoles.${review.role}`)}</strong>
        <small>{t(`bodyPhotos.results.reviewStates.${state}`)}</small>
      </div>
    </div>
  );
}
