import { afterEach, expect, it, vi } from "vitest";

import {
  MobileTelemetryLogger,
  configureMobileTelemetry,
  createCorrelationId,
  mobileLogger,
  redactLogData,
  redactLogMessage,
  type SentryCompatibleAdapter,
} from "./logging";

afterEach(() => {
  configureMobileTelemetry(null);
});

it("redacts tokens, credentials, identifiers, and sensitive media fields", () => {
  expect(redactLogData({
    access_token: "access-secret",
    email: "member@example.com",
    event: "upload_failed",
    image_uri: "file:///private/body.jpg",
    phone_number: "+989121234567",
  })).toEqual({
    access_token: "[REDACTED]",
    email: "[REDACTED]",
    event: "upload_failed",
    image_uri: "[REDACTED]",
    phone_number: "[REDACTED]",
  });
});

it("removes bearer and cookie values from arbitrary error text", () => {
  expect(redactLogMessage(
    "Bearer access-secret Cookie=fitician.auth.refresh-token=refresh-secret email=member@example.com",
  )).toBe("Bearer [REDACTED] Cookie=[REDACTED] email=[REDACTED]");
});

it("sends only allowlisted redacted context through the Sentry-compatible adapter", () => {
  const captureException = vi.fn<SentryCompatibleAdapter["captureException"]>();
  const captureMessage = vi.fn<SentryCompatibleAdapter["captureMessage"]>();
  const adapter = {
    captureException,
    captureMessage,
  } satisfies SentryCompatibleAdapter;
  const logger = new MobileTelemetryLogger(adapter, () => "corr-123");

  logger.captureMessage("native_request_completed", "info", {
    correlation_id: "corr-123",
    duration_ms: 42,
    email: "member@example.com",
    operation: "request",
    request_body: "medical text",
  });
  logger.captureException(
    "native_request_failed",
    new Error("Bearer secret-token email=member@example.com"),
    { http_status: 401, path: "/api/v1/profile/member-1" },
  );

  expect(adapter.captureMessage).toHaveBeenCalledWith(
    "native_request_completed",
    "info",
    {
      correlation_id: "corr-123",
      duration_ms: 42,
      event: "native_request_completed",
      operation: "request",
    },
  );
  const [safeError, context] = captureException.mock.calls[0] ?? [];
  expect(safeError?.message).toBe("Fitician mobile telemetry exception");
  expect(context).toEqual({
    correlation_id: "corr-123",
    error_type: "Error",
    http_status: 401,
    event: "native_request_failed",
  });
  expect(JSON.stringify(context)).not.toContain("member-1");
  expect(JSON.stringify(context)).not.toContain("medical");
  expect(JSON.stringify(context)).not.toContain("secret-token");
});

it("uses a UUID-shaped correlation id and the singleton can be configured", () => {
  expect(createCorrelationId()).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu,
  );
  const adapter = {
    captureException: vi.fn<SentryCompatibleAdapter["captureException"]>(),
    captureMessage: vi.fn<SentryCompatibleAdapter["captureMessage"]>(),
  } satisfies SentryCompatibleAdapter;
  configureMobileTelemetry(adapter);

  mobileLogger.captureMessage("native_request_completed", "info", {
    operation: "request",
  });

  expect(adapter.captureMessage).toHaveBeenCalledOnce();
  expect(adapter.captureMessage.mock.calls[0]?.[2]).toMatchObject({
    operation: "request",
    correlation_id: expect.any(String),
  });
});
