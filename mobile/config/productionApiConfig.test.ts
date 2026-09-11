import { expect, it } from "vitest";

import {
  PRODUCTION_API_BASE_URL,
  PRODUCTION_FRONTEND_ORIGIN,
  resolveApiBaseUrl,
  resolveFrontendOrigin,
} from "./productionApiConfig";

it("accepts only the configured Tailscale backend for production", () => {
  expect(resolveApiBaseUrl(PRODUCTION_API_BASE_URL, "production")).toBe(
    PRODUCTION_API_BASE_URL,
  );
  expect(() => resolveApiBaseUrl(undefined, "production")).toThrow(/Tailscale/u);
  expect(() => resolveApiBaseUrl("https://api.fitician.example", "production")).toThrow(
    /Tailscale/u,
  );
  expect(() => resolveApiBaseUrl("http://10.0.2.2:8001", "production")).toThrow(
    /Tailscale/u,
  );
  expect(() => resolveApiBaseUrl("http://192.168.1.107:8001", "production")).toThrow(
    /Tailscale/u,
  );
});

it("requires the configured trusted origin for production", () => {
  expect(resolveFrontendOrigin(PRODUCTION_FRONTEND_ORIGIN, "production")).toBe(
    PRODUCTION_FRONTEND_ORIGIN,
  );
  expect(() => resolveFrontendOrigin(undefined, "production")).toThrow(/required/u);
});

it("keeps development configuration explicit while allowing local development targets", () => {
  expect(resolveApiBaseUrl("http://10.0.2.2:8001", "development")).toBe(
    "http://10.0.2.2:8001",
  );
  expect(resolveFrontendOrigin("http://localhost:5173", "development")).toBe(
    "http://localhost:5173",
  );
});

it("fails closed when development configuration is missing", () => {
  expect(() => resolveApiBaseUrl(undefined, "development")).toThrow(/required/u);
  expect(() => resolveFrontendOrigin(undefined, "development")).toThrow(/required/u);
});
