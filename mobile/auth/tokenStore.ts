import * as SecureStore from "expo-secure-store";

import type { MobileAuthTokens, RefreshTokenStorage } from "@fitician/core";

export const REFRESH_TOKEN_KEY = "fitician.auth.refresh-token";

type AccessTokenInput = Pick<MobileAuthTokens, "access_token" | "expires_in">;

export class MemoryAccessTokenStore {
  private accessToken: string | null = null;
  private expiresAt = 0;

  constructor(private readonly now: () => number = Date.now) {}

  set(tokens: AccessTokenInput): void {
    this.accessToken = tokens.access_token;
    this.expiresAt = this.now() + tokens.expires_in * 1_000;
  }

  get(): string | null {
    if (this.accessToken === null || this.expiresAt <= this.now()) {
      this.clear();
      return null;
    }
    return this.accessToken;
  }

  clear(): void {
    this.accessToken = null;
    this.expiresAt = 0;
  }
}

export function createSecureRefreshTokenStore(
  key: string = REFRESH_TOKEN_KEY,
): RefreshTokenStorage {
  return {
    clear: () => SecureStore.deleteItemAsync(key),
    read: () => SecureStore.getItemAsync(key),
    write: (token) => SecureStore.setItemAsync(key, token),
  };
}
