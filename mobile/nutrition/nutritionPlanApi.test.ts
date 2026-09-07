import { expect, it } from "vitest";

import { ApiError, type BinaryDownload, type BinaryDownloadRequest, type TransportRequest } from "@fitician/core";

import {
  createNutritionPlanApi,
  type PlanBundleSelectionInput,
} from "./nutritionPlanApi";

function binaryDownload(): BinaryDownload {
  return {
    bytes: Uint8Array.from([37, 80, 68, 70]),
    contentType: "application/pdf",
    filename: "nutrition-plan.pdf",
  };
}

it("uses authenticated member nutrition plan endpoints", async () => {
  const requests: TransportRequest[] = [];
  const downloads: BinaryDownloadRequest[] = [];
  const api = createNutritionPlanApi(
    async <TResponse>(request: TransportRequest): Promise<TResponse> => {
      requests.push(request);
      return (request.path.endsWith("/history") ? [] : {}) as TResponse;
    },
    async (request: BinaryDownloadRequest): Promise<BinaryDownload> => {
      downloads.push(request);
      return binaryDownload();
    },
  );

  await api.getActive();
  await api.getLatest();
  await api.getLatestBundle();
  await api.generate();
  await api.getHistory();
  await api.get("plan/id");
  await api.selectBundle("bundle/id", { selected_plan_role: "budget" });
  await api.downloadPdf("plan/id");

  expect(requests).toEqual([
    { method: "GET", path: "/api/v1/nutrition/plans/active" },
    { method: "GET", path: "/api/v1/nutrition/plans/latest" },
    { method: "GET", path: "/api/v1/nutrition/plan-bundles/latest" },
    { method: "POST", path: "/api/v1/nutrition/plans" },
    { method: "GET", path: "/api/v1/nutrition/plans/history" },
    { method: "GET", path: "/api/v1/nutrition/plans/plan%2Fid" },
    {
      body: { selected_plan_role: "budget" },
      method: "POST",
      path: "/api/v1/nutrition/plan-bundles/bundle%2Fid/select",
    },
  ]);
  expect(downloads).toEqual([
    {
      method: "GET",
      path: "/api/v1/nutrition/plans/plan%2Fid/pdf",
      responseType: "binary",
    },
  ]);
});

it("sends the generated bundle selection contract without reshaping it", async () => {
  const requests: TransportRequest[] = [];
  const api = createNutritionPlanApi(
    async <TResponse>(request: TransportRequest): Promise<TResponse> => {
      requests.push(request);
      return {} as TResponse;
    },
    async () => binaryDownload(),
  );
  const input: PlanBundleSelectionInput = {
    plan_id: "plan-1",
    plan_role: "ideal",
    selected_plan_id: "plan-1",
    selected_plan_role: "ideal",
  };

  await api.selectBundle("bundle-1", input);

  expect(requests).toEqual([
    {
      body: input,
      method: "POST",
      path: "/api/v1/nutrition/plan-bundles/bundle-1/select",
    },
  ]);
});

it("treats only missing latest and active plans as empty", async () => {
  const api = createNutritionPlanApi(
    async <TResponse>(request: TransportRequest): Promise<TResponse> => {
      throw new ApiError(404, request.path);
    },
    async () => binaryDownload(),
  );

  await expect(api.getActive()).resolves.toBeNull();
  await expect(api.getLatest()).resolves.toBeNull();
  await expect(api.getLatestBundle()).resolves.toBeNull();
  await expect(api.get("missing")).rejects.toMatchObject({ status: 404 });
});

it("preserves non-404 nutrition plan failures", async () => {
  const api = createNutritionPlanApi(
    async <TResponse>(request: TransportRequest): Promise<TResponse> => {
      throw new ApiError(503, request.path);
    },
    async () => binaryDownload(),
  );

  await expect(api.getActive()).rejects.toMatchObject({ status: 503 });
  await expect(api.getLatestBundle()).rejects.toMatchObject({ status: 503 });
});
