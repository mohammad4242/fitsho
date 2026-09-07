import type { TransportRequest } from "@fitician/core";

import type { MobileSpecialistAccess } from "../ui/navigation/routePolicy";

export type SpecialistAccessRequest = <TResponse>(
  request: TransportRequest,
) => Promise<TResponse>;

export type SpecialistAccessSnapshot = {
  readonly coach: MobileSpecialistAccess;
  readonly physician: MobileSpecialistAccess;
};

type AccessResponse = { readonly authorized?: unknown };

const accessPaths = {
  coach: "/api/v1/coach/workout-reviews/access",
  physician: "/api/v1/nutrition/physician/access",
} as const;

async function isAuthorized(
  request: SpecialistAccessRequest,
  path: string,
): Promise<MobileSpecialistAccess> {
  try {
    const response = await request<AccessResponse>({ method: "GET", path });
    return response.authorized === true ? "granted" : "denied";
  } catch {
    return "denied";
  }
}

export async function loadSpecialistAccess(
  request: SpecialistAccessRequest,
): Promise<SpecialistAccessSnapshot> {
  const [coach, physician] = await Promise.all([
    isAuthorized(request, accessPaths.coach),
    isAuthorized(request, accessPaths.physician),
  ]);
  return { coach, physician };
}
