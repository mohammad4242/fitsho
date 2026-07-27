import type { TFunction } from "i18next";

import { ApiError } from "../../shared/apiClient";

export function authErrorMessage(error: unknown, t: TFunction): string {
  if (error instanceof TypeError) {
    return t("errors.network");
  }
  if (error instanceof ApiError && error.status === 401) {
    return t("errors.invalidCredentials");
  }
  if (error instanceof ApiError && error.status === 409) {
    return t("errors.duplicateEmail");
  }
  return t("errors.generic");
}
