import { useTranslation } from "react-i18next";

import type { SpecialistReviewState } from "./types";

export function SpecialistReviewStatus({ review }: { review: SpecialistReviewState }) {
  const { t } = useTranslation();
  const state = review.decision ?? "pending";

  return (
    <div
      className={`body-analysis-review body-analysis-review--${state}`}
      aria-label={t("bodyPhotos.results.reviewAria", {
        role: t(`bodyPhotos.results.reviewRoles.${review.role}`),
        state: t(`bodyPhotos.results.reviewStates.${state}`),
      })}
    >
      <span className="body-analysis-review__dot" aria-hidden="true" />
      <div>
        <strong>{t("bodyAnalysis.review.roleLabel", {
          role: t(`bodyPhotos.results.reviewRoles.${review.role}`),
        })}</strong>
        <small>{t(`bodyPhotos.results.reviewStates.${state}`)}</small>
      </div>
    </div>
  );
}
