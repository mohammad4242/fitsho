import { expect, it, vi } from "vitest";

import { createNativeTransport } from "./nativeTransport";
import {
  MobileTelemetryLogger,
  type MobileLogger,
  type SentryCompatibleAdapter,
} from "../platform/logging";

const fileSystem = vi.hoisted(() => {
  const fileConstructor = vi.fn();
  const fileWrite = vi.fn();
  class MockFile {
    readonly uri: string;
    readonly bytes = vi.fn(async () => Uint8Array.from([1, 2, 3]));
    readonly write = fileWrite;
    readonly delete = vi.fn();

    constructor(...uris: unknown[]) {
      fileConstructor();
      const directory = uris[0] as { uri?: string } | undefined;
      this.uri = `${directory?.uri ?? "file:///cache/"}${String(uris[1] ?? "upload.bin")}`;
    }
  }

  return {
    File: MockFile,
    Paths: { cache: { uri: "file:///cache/" } },
    fileConstructor,
    fileWrite,
  };
});

vi.mock("expo-file-system", () => fileSystem);

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

it("serializes multipart bytes without native temporary files", async () => {
  const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
    new Response(JSON.stringify({ uploaded: true }), { status: 200 }),
  );
  const transport = createNativeTransport({
    apiBaseUrl: "https://api.fitician.example",
    fetchImpl,
  });
  const originalTextEncoder = globalThis.TextEncoder;
  Object.defineProperty(globalThis, "TextEncoder", { configurable: true, value: undefined });
  try {
    await expect(transport.upload({
      method: "PUT",
      parts: [{
        bytes: Uint8Array.from([1, 2, 3]),
        contentType: "image/jpeg",
        filename: "body-front.jpg",
        name: "file",
      }],
      path: "/api/v1/body-photo-sessions/session-1/photos/front",
    })).resolves.toEqual({ uploaded: true });
  } finally {
    Object.defineProperty(globalThis, "TextEncoder", {
      configurable: true,
      value: originalTextEncoder,
    });
  }

  const [, init] = fetchImpl.mock.calls[0];
  const body = init?.body;
  expect(body).toBeInstanceOf(Uint8Array);
  const serialized = new TextDecoder().decode(body as Uint8Array);
  expect(serialized).toContain('name="file"; filename="body-front.jpg"');
  expect(serialized).toContain("Content-Type: image/jpeg");
  expect((init?.headers as Headers).get("Content-Type")).toMatch(
    /^multipart\/form-data; boundary=----FiticianBoundary/u,
  );
  expect(fileSystem.fileConstructor).not.toHaveBeenCalled();
  expect(fileSystem.fileWrite).not.toHaveBeenCalled();
});

it("does not pass the upload manager signal to native fetch", async () => {
  const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
    new Response(JSON.stringify({ uploaded: true }), { status: 200 }),
  );
  const transport = createNativeTransport({
    apiBaseUrl: "https://api.fitician.example",
    fetchImpl,
  });

  await transport.upload({
    method: "POST",
    parts: [{
      bytes: Uint8Array.from([1, 2, 3]),
      contentType: "image/jpeg",
      filename: "food-photo.jpg",
      name: "file",
    }],
    path: "/api/v1/nutrition/tracking/photo-estimates?language=fa",
    signal: { aborted: false },
  });

  const [, init] = fetchImpl.mock.calls[0];
  expect(init?.signal).toBeUndefined();
});
