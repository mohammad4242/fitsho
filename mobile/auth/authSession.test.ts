import { expect, it, vi } from "vitest";

import { ApiError, type FiticianTransport, type MobileAuthTokens, type TransportRequest } from "@fitician/core";

import { MobileAuthSession } from "./authSession";
import type { MobileAuthApi } from "./authApi";

vi.mock("expo-secure-store", () => ({
  deleteItemAsync: vi.fn(),
  getItemAsync: vi.fn(),
  setItemAsync: vi.fn(),
}));

const tokens: MobileAuthTokens = {
  access_token: "access-token",
  expires_in: 900,
  refresh_expires_in: 2_592_000,
  refresh_token: "refresh-token",
  token_type: "Bearer",
  user: {
    created_at: "2026-01-01T00:00:00Z",
    email: "member@example.com",
    id: "member-1",
    is_admin: false,
    phone_number: null,
  },
};

function api(): MobileAuthApi {
  return {
    forgotPassword: async () => ({ message: "ok" }),
    register: async () => tokens.user,
    resetPassword: async () => undefined,
    sendPhoneOtp: async () => ({ message: "ok", retry_after_seconds: 60 }),
    signInWithGoogle: async () => tokens,
    signInWithPassword: async () => tokens,
    verifyEmail: async () => undefined,
    verifyPhoneOtp: async () => tokens,
  };
}

function transport(): FiticianTransport {
  return {
    download: async () => ({ bytes: new Uint8Array(), contentType: null, filename: null }),
    request: async <TResponse>(request: TransportRequest) => {
      if (request.path.endsWith("/refresh")) {
        return tokens as TResponse;
      }
      return undefined as TResponse;
    },
    upload: async <TResponse>(_request: unknown) => undefined as TResponse,
  };
}

it("restores the user from a rotating refresh token and publishes signed-in state", async () => {
  const session = new MobileAuthSession({
    api: api(),
    refreshTokenStorage: {
      clear: async () => undefined,
      read: async () => "stored-refresh-token",
      write: async () => undefined,
    },
    transport: transport(),
  });
  const states = [session.getSnapshot()];
  session.subscribe((state) => states.push(state));

  await session.restore();

  expect(session.getSnapshot()).toMatchObject({ status: "signed_in", user: tokens.user });
  expect(states.at(-1)).toMatchObject({ status: "signed_in" });
});

it("expires the session and notifies subscribers after a rejected refresh", async () => {
  const session = new MobileAuthSession({
    api: api(),
    refreshTokenStorage: {
      clear: async () => undefined,
      read: async () => "revoked-refresh-token",
      write: async () => undefined,
    },
    transport: {
      ...transport(),
      request: async () => {
        throw new ApiError(401, "Invalid refresh token");
      },
    },
  });

  await session.restore();

  expect(session.getSnapshot()).toMatchObject({
    sessionExpired: true,
    status: "signed_out",
    user: null,
  });
});

it("registers through the shared endpoint and then establishes native tokens", async () => {
  const calls: string[] = [];
  const session = new MobileAuthSession({
    api: {
      ...api(),
      register: async () => {
        calls.push("register");
        return tokens.user;
      },
      signInWithPassword: async () => {
        calls.push("password");
        return tokens;
      },
    },
    refreshTokenStorage: {
      clear: async () => undefined,
      read: async () => null,
      write: async () => undefined,
    },
    transport: transport(),
  });

  await expect(
    session.register({ email: "member@example.com", password: "long password" }),
  ).resolves.toEqual(tokens.user);
  expect(calls).toEqual(["register", "password"]);
  expect(session.getSnapshot()).toMatchObject({ status: "signed_in" });
});
