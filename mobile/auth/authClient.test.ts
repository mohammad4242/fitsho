import { expect, it, vi } from "vitest";

import { ApiError, type TransportRequest } from "@fitician/core";

import { MobileAuthClient } from "./authClient";

vi.mock("expo-secure-store", () => ({
  deleteItemAsync: vi.fn(),
  getItemAsync: vi.fn(),
  setItemAsync: vi.fn(),
}));

it("refreshes concurrent unauthorized requests through one refresh call", async () => {
  let refreshCalls = 0;

  const client = new MobileAuthClient({
    refreshTokenStorage: {
      clear: async () => undefined,
      read: async () => "refresh-token",
      write: async () => undefined,
    },
    transport: {
      download: async () => ({ bytes: new Uint8Array(), contentType: null, filename: null }),
      request: async <TResponse>(request: TransportRequest): Promise<TResponse> => {
        if (request.path.endsWith("/refresh")) {
          refreshCalls += 1;
          return {
            access_token: "refreshed-access",
            expires_in: 900,
            refresh_expires_in: 2_592_000,
            refresh_token: "rotated-refresh",
            token_type: "Bearer" as const,
            user: {
              created_at: "2026-01-01T00:00:00Z",
              email: "member@example.com",
              id: "member-1",
              is_admin: false,
              phone_number: null,
            },
          } as TResponse;
        }
        if (request.headers?.Authorization === "Bearer refreshed-access") {
          return { ok: true } as TResponse;
        }
        throw new ApiError(401, "Authentication required");
      },
      upload: async <TResponse>(): Promise<TResponse> => ({ ok: true }) as TResponse,
    },
  });

  const [first, second] = await Promise.all([
    client.request<{ ok: boolean }>({ path: "/api/v1/member", method: "GET" }),
    client.request<{ ok: boolean }>({ path: "/api/v1/member", method: "GET" }),
  ]);

  expect(first).toEqual(second);
  expect(first).toEqual({ ok: true });
  expect(refreshCalls).toBe(1);
});

it("refreshes inside the configured clock-skew window", async () => {
  let now = 1_000;
  let refreshCalls = 0;
  let staleAccessCalls = 0;
  let storedRefreshToken: string | null = "initial-refresh";
  const client = new MobileAuthClient({
    now: () => now,
    clockSkewMilliseconds: 30_000,
    refreshTokenStorage: {
      clear: async () => {
        storedRefreshToken = null;
      },
      read: async () => storedRefreshToken,
      write: async (token) => {
        storedRefreshToken = token;
      },
    },
    transport: {
      download: async () => ({ bytes: new Uint8Array(), contentType: null, filename: null }),
      request: async <TResponse>(request: TransportRequest): Promise<TResponse> => {
        if (request.path.endsWith("/refresh")) {
          refreshCalls += 1;
          return {
            access_token: "fresh-access",
            expires_in: 900,
            refresh_expires_in: 2_592_000,
            refresh_token: "fresh-refresh",
            token_type: "Bearer" as const,
            user: {
              created_at: "2026-01-01T00:00:00Z",
              email: "member@example.com",
              id: "member-1",
              is_admin: false,
              phone_number: null,
            },
          } as TResponse;
        }
        if (request.headers?.Authorization === "Bearer fresh-access") {
          return { ok: true } as TResponse;
        }
        staleAccessCalls += 1;
        throw new ApiError(401, "Authentication required");
      },
      upload: async <TResponse>(): Promise<TResponse> => ({ ok: true }) as TResponse,
    },
  });

  await client.setSession({
    access_token: "soon-expired-access",
    expires_in: 20,
    refresh_expires_in: 2_592_000,
    refresh_token: "initial-refresh",
    token_type: "Bearer",
    user: {
      created_at: "2026-01-01T00:00:00Z",
      email: "member@example.com",
      id: "member-1",
      is_admin: false,
      phone_number: null,
    },
  });
  now += 1;

  await expect(client.request<{ ok: boolean }>({ path: "/api/v1/member", method: "GET" })).resolves
    .toEqual({ ok: true });
  expect(refreshCalls).toBe(1);
  expect(staleAccessCalls).toBe(0);
});

it("clears a revoked session and notifies once", async () => {
  let clearCalls = 0;
  let expiryNotifications = 0;
  const client = new MobileAuthClient({
    onSessionExpired: () => {
      expiryNotifications += 1;
    },
    refreshTokenStorage: {
      clear: async () => {
        clearCalls += 1;
      },
      read: async () => "revoked-refresh",
      write: async () => undefined,
    },
    transport: {
      download: async () => ({ bytes: new Uint8Array(), contentType: null, filename: null }),
      request: async <TResponse>(): Promise<TResponse> => {
        throw new ApiError(401, "Refresh token is invalid");
      },
      upload: async <TResponse>(): Promise<TResponse> => ({ ok: true }) as TResponse,
    },
  });

  await expect(client.restoreSession()).resolves.toBe(false);
  expect(clearCalls).toBe(1);
  expect(expiryNotifications).toBe(1);
});

it("retries one unauthorized request and expires after a second 401", async () => {
  let refreshCalls = 0;
  let clearCalls = 0;
  let expiryNotifications = 0;
  let storedRefreshToken: string | null = "initial-refresh";
  const client = new MobileAuthClient({
    onSessionExpired: () => {
      expiryNotifications += 1;
    },
    refreshTokenStorage: {
      clear: async () => {
        clearCalls += 1;
        storedRefreshToken = null;
      },
      read: async () => storedRefreshToken,
      write: async (token) => {
        storedRefreshToken = token;
      },
    },
    transport: {
      download: async () => ({ bytes: new Uint8Array(), contentType: null, filename: null }),
      request: async <TResponse>(request: TransportRequest): Promise<TResponse> => {
        if (request.path.endsWith("/refresh")) {
          refreshCalls += 1;
          return {
            access_token: "fresh-access",
            expires_in: 900,
            refresh_expires_in: 2_592_000,
            refresh_token: "fresh-refresh",
            token_type: "Bearer" as const,
            user: {
              created_at: "2026-01-01T00:00:00Z",
              email: "member@example.com",
              id: "member-1",
              is_admin: false,
              phone_number: null,
            },
          } as TResponse;
        }
        throw new ApiError(401, "Authentication required");
      },
      upload: async <TResponse>(): Promise<TResponse> => ({ ok: true }) as TResponse,
    },
  });

  await client.setSession({
    access_token: "initial-access",
    expires_in: 900,
    refresh_expires_in: 2_592_000,
    refresh_token: "initial-refresh",
    token_type: "Bearer",
    user: {
      created_at: "2026-01-01T00:00:00Z",
      email: "member@example.com",
      id: "member-1",
      is_admin: false,
      phone_number: null,
    },
  });

  await expect(client.request({ path: "/api/v1/member", method: "GET" })).rejects.toMatchObject({
    status: 401,
  });
  expect(refreshCalls).toBe(1);
  expect(clearCalls).toBe(1);
  expect(expiryNotifications).toBe(1);
});

it("does not repeat a rejected refresh during one request", async () => {
  let refreshCalls = 0;
  let clearCalls = 0;
  const client = new MobileAuthClient({
    refreshTokenStorage: {
      clear: async () => {
        clearCalls += 1;
      },
      read: async () => "revoked-refresh",
      write: async () => undefined,
    },
    transport: {
      download: async () => ({ bytes: new Uint8Array(), contentType: null, filename: null }),
      request: async <TResponse>(request: TransportRequest): Promise<TResponse> => {
        if (request.path.endsWith("/refresh")) {
          refreshCalls += 1;
          throw new ApiError(401, "Refresh token is invalid");
        }
        throw new ApiError(401, "Authentication required");
      },
      upload: async <TResponse>(): Promise<TResponse> => ({ ok: true }) as TResponse,
    },
  });

  await expect(client.request({ path: "/api/v1/member", method: "GET" })).rejects.toMatchObject({
    status: 401,
  });
  expect(refreshCalls).toBe(1);
  expect(clearCalls).toBe(1);
});
