import type { ProfileStatusResponse } from "@fitician/core/profile";

import type { TransportRequest } from "@fitician/core";
import { logDevelopmentDiagnostic } from "../../platform/logging";

export type MobileProfileRouteState =
  | {
      readonly completionState: null;
      readonly productMode: null;
      readonly status: "loading" | "error";
    }
  | {
      readonly completionState: ProfileStatusResponse["completion_state"];
      readonly productMode: ProfileStatusResponse["product_mode"];
      readonly status: "resolved";
    };

export type MobileProfileStatusRequest = <TResponse>(
  request: TransportRequest,
) => Promise<TResponse>;

export const mobileProfileLoadingState: MobileProfileRouteState = {
  completionState: null,
  productMode: null,
  status: "loading",
};

export const mobileProfileErrorState: MobileProfileRouteState = {
  completionState: null,
  productMode: null,
  status: "error",
};

export function mobileProfileStateFromStatus(
  status: ProfileStatusResponse,
): MobileProfileRouteState {
  return {
    completionState: status.completion_state,
    productMode: status.product_mode,
    status: "resolved",
  };
}

function diagnosticErrorContext(error: unknown): {
  readonly error_type: string;
  readonly http_status?: number;
} {
  const errorType = error instanceof Error && error.name.length > 0 ? error.name : typeof error;
  const status = typeof error === "object" && error !== null && "status" in error
    ? (error as { readonly status?: unknown }).status
    : undefined;
  return {
    error_type: errorType,
    ...(typeof status === "number" ? { http_status: status } : {}),
  };
}

export async function loadMobileProfileStatus(
  request: MobileProfileStatusRequest,
): Promise<MobileProfileRouteState> {
  try {
    const status = await request<ProfileStatusResponse>({
      method: "GET",
      path: "/api/v1/profile/status",
    });
    return mobileProfileStateFromStatus(status);
  } catch (error) {
    logDevelopmentDiagnostic("profile_bootstrap_failed", "error", {
      operation: "profile_status",
      ...diagnosticErrorContext(error),
    });
    return mobileProfileErrorState;
  }
}
