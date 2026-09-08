import { expect, it } from "vitest";

import { ApiError, type TransportRequest } from "@fitician/core";

import { loadSpecialistAccess } from "./specialistAccess";

it("grants only the specialist roles confirmed by their backend access endpoints", async () => {
  const requests: TransportRequest[] = [];
  const access = await loadSpecialistAccess(async <TResponse>(request: TransportRequest) => {
    requests.push(request);
    if (request.path === "/api/v1/nutrition/physician/access") {
      return { authorized: true } as TResponse;
    }
    return { authorized: false } as TResponse;
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
  ).resolves.toEqual({ coach: "error", physician: "error" });
});

it("treats a valid forbidden response as denied but server failures as errors", async () => {
  await expect(
    loadSpecialistAccess(async (request: TransportRequest) => {
      if (request.path === "/api/v1/coach/workout-reviews/access") {
        throw new ApiError(403, "Forbidden");
      }
      throw new ApiError(503, "Unavailable");
    }),
  ).resolves.toEqual({ coach: "denied", physician: "error" });
});

it("treats malformed access responses as errors", async () => {
  await expect(
    loadSpecialistAccess(async <TResponse>() => ({ authorized: "yes" } as TResponse)),
  ).resolves.toEqual({ coach: "error", physician: "error" });
});

it("returns granted access after a retry succeeds", async () => {
  let attempt = 0;
  const request = async <TResponse>(_input: TransportRequest) => {
    attempt += 1;
    if (attempt <= 2) throw new Error("temporary outage");
    return { authorized: true } as TResponse;
  };

  await expect(loadSpecialistAccess(request)).resolves.toEqual({ coach: "error", physician: "error" });
  await expect(loadSpecialistAccess(request)).resolves.toEqual({ coach: "granted", physician: "granted" });
});
