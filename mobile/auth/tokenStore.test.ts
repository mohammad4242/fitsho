import { afterEach, expect, it, vi } from "vitest";

import * as SecureStore from "expo-secure-store";

import { createSecureRefreshTokenStore, MemoryAccessTokenStore } from "./tokenStore";

vi.mock("expo-secure-store", () => ({
  deleteItemAsync: vi.fn(),
  getItemAsync: vi.fn(),
  setItemAsync: vi.fn(),
}));

afterEach(() => vi.clearAllMocks());

it("keeps access tokens in memory and expires them from an injected clock", () => {
  let now = 1_000;
  const store = new MemoryAccessTokenStore(() => now);

  store.set({
    access_token: "access-token",
    expires_in: 900,
  });
  expect(store.get()).toBe("access-token");

  now += 900_000;
  expect(store.get()).toBeNull();
});

it("stores only the refresh token through SecureStore", async () => {
  vi.mocked(SecureStore.getItemAsync).mockResolvedValue("stored-refresh-token");
  const store = createSecureRefreshTokenStore();

  await expect(store.read()).resolves.toBe("stored-refresh-token");
  await store.write("new-refresh-token");
  await store.clear();

  expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
    "fitician.auth.refresh-token",
    "new-refresh-token",
  );
  expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith("fitician.auth.refresh-token");
});
