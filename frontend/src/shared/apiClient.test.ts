import { afterEach, expect, it, vi } from "vitest";

import { ApiError, request } from "./apiClient";

afterEach(() => vi.restoreAllMocks());

it("always includes cookies and JSON headers", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );

  await request<{ ok: boolean }>("/api/test", { method: "POST", body: "{}" });

  expect(fetch).toHaveBeenCalledWith(
    "/api/test",
    expect.objectContaining({
      credentials: "include",
      headers: expect.objectContaining({ "Content-Type": "application/json" }),
    }),
  );
});

it("maps HTTP failures and empty success responses", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Conflict" }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
    )
    .mockResolvedValueOnce(new Response(null, { status: 204 }));

  await expect(request("/api/fail")).rejects.toEqual(new ApiError(409, "Conflict"));
  await expect(request<void>("/api/empty")).resolves.toBeUndefined();
});

it("uses the generic message for structured validation details", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ detail: [{ msg: "Invalid value" }] }), {
      status: 422,
      headers: { "Content-Type": "application/json" },
    }),
  );

  await expect(request("/api/validation-error")).rejects.toEqual(
    new ApiError(422, "Request failed"),
  );
});
