import { afterEach, expect, it } from "vitest";

import { ApiError } from "@fitician/core";

import {
  mobileQueryDefaults,
  mobileRetryDelay,
  shouldRetryMobileQuery,
} from "./queryDefaults";

afterEach(() => undefined);

it("does not retry authentication, permission, validation, or offline failures", () => {
  expect(shouldRetryMobileQuery(0, new ApiError(401, "expired"), true)).toBe(false);
  expect(shouldRetryMobileQuery(0, new ApiError(403, "forbidden"), true)).toBe(false);
  expect(shouldRetryMobileQuery(0, new ApiError(422, "invalid"), true)).toBe(false);
  expect(shouldRetryMobileQuery(0, new Error("offline"), false)).toBe(false);
});

it("limits transient retries with bounded exponential backoff", () => {
  expect(shouldRetryMobileQuery(0, new ApiError(500, "server"), true)).toBe(true);
  expect(shouldRetryMobileQuery(2, new ApiError(500, "server"), true)).toBe(false);
  expect(shouldRetryMobileQuery(0, new Error("network"), true)).toBe(true);
  expect(mobileRetryDelay(0)).toBe(1_000);
  expect(mobileRetryDelay(1)).toBe(2_000);
  expect(mobileRetryDelay(10)).toBe(30_000);
});

it("does not silently queue generic mutations", () => {
  expect(mobileQueryDefaults.queries?.networkMode).toBe("online");
  expect(mobileQueryDefaults.mutations?.networkMode).toBe("always");
  expect(mobileQueryDefaults.mutations?.retry).toBe(false);
});
