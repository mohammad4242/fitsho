import { expect, it, vi } from "vitest";

import { createNativeTransport } from "./nativeTransport";
import {
  MobileTelemetryLogger,
  type MobileLogger,
  type SentryCompatibleAdapter,
} from "../platform/logging";

it("builds native requests from the configured API origin", async () => {
  const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
    new Response(JSON.stringify({ ok: true }), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    }),
  );
  const transport = createNativeTransport({
    apiBaseUrl: "https://api.fitician.example/",
    fetchImpl,
    trustedOrigin: "https://fitician.example",
  });

  await expect(
    transport.request<{ ok: boolean }>({
      body: { email: "member@example.com" },
      method: "POST",
      path: "/api/v1/auth/register",
    }),
  ).resolves.toEqual({ ok: true });

  const [, init] = fetchImpl.mock.calls[0];
  expect(init).toMatchObject({
    body: JSON.stringify({ email: "member@example.com" }),
    method: "POST",
  });
  const headers = init?.headers as Headers;
  expect(headers.get("Content-Type")).toBe("application/json");
  expect(headers.get("Origin")).toBe("https://fitician.example");
});

it("converts API error payloads into the shared ApiError", async () => {
  const transport = createNativeTransport({
    apiBaseUrl: "https://api.fitician.example",
    fetchImpl: vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ detail: { code: "AUTH_INVALID", message: "Invalid" } }), {
        headers: { "Content-Type": "application/json" },
        status: 401,
      }),
    ),
  });

  await expect(transport.request({ method: "GET", path: "/api/v1/auth/me" })).rejects.toMatchObject({
    code: "AUTH_INVALID",
    message: "Invalid",
    status: 401,
  });
});

it("adds a correlation id and emits redacted request telemetry", async () => {
  const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
    new Response(JSON.stringify({ ok: true }), { status: 200 }),
  );
  const logger = {
    captureException: vi.fn<MobileLogger["captureException"]>(),
    captureMessage: vi.fn<MobileLogger["captureMessage"]>(),
  } satisfies MobileLogger;
  const transport = createNativeTransport({
    apiBaseUrl: "https://api.fitician.example",
    correlationIdFactory: () => "corr-request-1",
    fetchImpl,
    logger,
  });

  await transport.request({
    body: { email: "member@example.com" },
    method: "POST",
    path: "/api/v1/auth/register/member-1",
  });

  const [, init] = fetchImpl.mock.calls[0];
  expect((init?.headers as Headers).get("X-Correlation-ID")).toBe("corr-request-1");
  expect(logger.captureMessage).toHaveBeenCalledWith(
    "native_request_completed",
    "info",
    expect.objectContaining({
      correlation_id: "corr-request-1",
      method: "POST",
      operation: "request",
      http_status: 200,
    }),
  );
  expect(JSON.stringify(logger.captureMessage.mock.calls[0])).not.toContain("member-1");
  expect(JSON.stringify(logger.captureMessage.mock.calls[0])).not.toContain("member@example.com");
});

it("reports failed HTTP requests without sending response details", async () => {
  const captureException = vi.fn<SentryCompatibleAdapter["captureException"]>();
  const adapter = {
    captureException,
    captureMessage: vi.fn<SentryCompatibleAdapter["captureMessage"]>(),
  } satisfies SentryCompatibleAdapter;
  const logger = new MobileTelemetryLogger(adapter, () => "corr-failure-1");
  const transport = createNativeTransport({
    apiBaseUrl: "https://api.fitician.example",
    correlationIdFactory: () => "corr-failure-1",
    fetchImpl: vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({ detail: { code: "PROFILE_PRIVATE", message: "member@example.com" } }),
        { status: 403 },
      ),
    ),
    logger,
  });

  await expect(transport.request({ method: "GET", path: "/api/v1/profile/member-1" })).rejects.toThrow();

  expect(captureException).toHaveBeenCalledWith(
    expect.any(Error),
    expect.objectContaining({
      correlation_id: "corr-failure-1",
      http_status: 403,
      event: "native_request_failed",
      operation: "request",
    }),
  );
  expect(JSON.stringify(captureException.mock.calls[0])).not.toContain("member@example.com");
  expect(JSON.stringify(captureException.mock.calls[0])).not.toContain("PROFILE_PRIVATE");
});
