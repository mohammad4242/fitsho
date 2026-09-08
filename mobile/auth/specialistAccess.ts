import type { TransportRequest } from "@fitician/core";

import { logDevelopmentDiagnostic } from "../platform/logging";
import type { MobileSpecialistAccess } from "../ui/navigation/routePolicy";

export type SpecialistAccessRequest = <TResponse>(
  request: TransportRequest,
) => Promise<TResponse>;

export type SpecialistAccessSnapshot = {
  readonly coach: MobileSpecialistAccess;
  readonly physician: MobileSpecialistAccess;
};

type AccessResponse = { readonly authorized?: unknown };

function isForbiddenResponse(error: unknown): boolean {
  return typeof error === "object"
    && error !== null
    && "status" in error
    && (error as { readonly status?: unknown }).status === 403;
}

const accessPaths = {
  coach: "/api/v1/coach/workout-reviews/access",
  physician: "/api/v1/nutrition/physician/access",
} as const;

async function isAuthorized(
  request: SpecialistAccessRequest,
  path: string,
  role: "coach" | "physician",
): Promise<MobileSpecialistAccess> {
  try {
    const response = await request<AccessResponse>({ method: "GET", path });
    if (response.authorized === true) return "granted";
    if (response.authorized === false) return "denied";
    logDevelopmentDiagnostic("specialist_access_failed", "error", {
      error_type: "InvalidAccessResponse",
      operation: "specialist_access",
      role,
    });
    return "error";
  } catch (error) {
    if (isForbiddenResponse(error)) return "denied";
    logDevelopmentDiagnostic("specialist_access_failed", "error", {
      error_type: error instanceof Error && error.name.length > 0 ? error.name : typeof error,
      http_status: typeof error === "object" && error !== null && "status" in error
        ? (error as { readonly status?: unknown }).status
        : undefined,
      operation: "specialist_access",
      role,
    });
    return "error";
  }
}

export async function loadSpecialistAccess(
  request: SpecialistAccessRequest,
): Promise<SpecialistAccessSnapshot> {
  const [coach, physician] = await Promise.all([
    isAuthorized(request, accessPaths.coach, "coach"),
    isAuthorized(request, accessPaths.physician, "physician"),
  ]);
  return { coach, physician };
}
