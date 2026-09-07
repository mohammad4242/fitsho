import { expect, it, vi } from "vitest";

import { createNativeTransport } from "./nativeTransport";

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
