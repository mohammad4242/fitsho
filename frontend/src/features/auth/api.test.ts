import { afterEach, describe, expect, it, vi } from "vitest";

import * as authApi from "./api";
import { getCurrentUser, login, logout, register } from "./api";

const user = {
  id: "018f0000-0000-7000-8000-000000000001",
  email: "user@example.com",
  phone_number: null,
  created_at: "2026-07-24T00:00:00Z",
  is_admin: false,
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

  it("calls password recovery and phone OTP endpoints", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ message: "accepted" }), {
          status: 202,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ message: "accepted", retry_after_seconds: 60 }),
          { status: 202, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...user, email: null, phone_number: "+989123456789" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    await authApi.forgotPassword("user@example.com");
    await authApi.resetPassword("raw-token", "new password");
    await authApi.sendPhoneOtp("09123456789");
    await authApi.verifyPhoneOtp("09123456789", "123456");

    expect(fetch).toHaveBeenNthCalledWith(
      1,
      "/api/v1/auth/forgot-password",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetch).toHaveBeenNthCalledWith(
      2,
      "/api/v1/auth/reset-password",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetch).toHaveBeenNthCalledWith(
      3,
      "/api/v1/auth/phone/send-otp",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetch).toHaveBeenNthCalledWith(
      4,
      "/api/v1/auth/phone/verify-otp",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
