import { expect, it } from "vitest";

import type { TransportRequest } from "@fitician/core";

import { loadSpecialistAccess } from "./specialistAccess";

it("grants only the specialist roles confirmed by their backend access endpoints", async () => {
  const requests: TransportRequest[] = [];
  const access = await loadSpecialistAccess(async <TResponse>(request: TransportRequest) => {
    requests.push(request);
    if (request.path === "/api/v1/nutrition/physician/access") {
      return { authorized: true } as TResponse;
    }
    throw new Error("forbidden");
  });

  expect(access).toEqual({ coach: "denied", physician: "granted" });
  expect(requests.map((request) => request.path).sort()).toEqual([
    "/api/v1/coach/workout-reviews/access",
    "/api/v1/nutrition/physician/access",
  ]);
});

it("does not expose a role when its access check fails", async () => {
  await expect(
    loadSpecialistAccess(async () => {
      throw new Error("offline");
    }),
  ).resolves.toEqual({ coach: "denied", physician: "denied" });
});
