import { afterEach, describe, expect, it, vi } from "vitest";

import { getCurrentUser, login, logout, register } from "./api";

const user = {
  id: "018f0000-0000-7000-8000-000000000001",
  email: "user@example.com",
  created_at: "2026-07-24T00:00:00Z",
};

afterEach(() => vi.restoreAllMocks());

describe("auth api", () => {
  it("always includes browser credentials", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(user), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await register({ email: user.email, password: "long password" });

    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/auth/register",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("maps an unauthorized current-user response to null", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 401 }),
    );

    await expect(getCurrentUser()).resolves.toBeNull();
  });

  it("calls login and logout endpoints", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify(user), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(
      login({ email: user.email, password: "long password" }),
    ).resolves.toEqual(user);
    await expect(logout()).resolves.toBeUndefined();
  });
});
