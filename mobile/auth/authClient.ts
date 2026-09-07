import {
  ApiError,
  type BinaryDownload,
  type BinaryDownloadRequest,
  type FiticianTransport,
  type MobileAuthTokens,
  type RefreshTokenStorage,
  type TransportRequest,
} from "@fitician/core";
import type { User } from "@fitician/core/auth";

import { MemoryAccessTokenStore } from "./tokenStore";

const DEFAULT_CLOCK_SKEW_MILLISECONDS = 30_000;
const DEFAULT_REFRESH_PATH = "/api/v1/auth/mobile/refresh";

type RefreshOutcome = "refreshed" | "missing" | "rejected";

export interface MobileAuthClientOptions {
  transport: FiticianTransport;
  refreshTokenStorage: RefreshTokenStorage;
  accessTokenStore?: MemoryAccessTokenStore;
  now?: () => number;
  clockSkewMilliseconds?: number;
  refreshPath?: string;
  onSessionExpired?: () => void | Promise<void>;
}

export class MobileAuthClient {
  private readonly transport: FiticianTransport;
  private readonly refreshTokenStorage: RefreshTokenStorage;
  private readonly accessTokenStore: MemoryAccessTokenStore;
  private readonly clockSkewMilliseconds: number;
  private readonly refreshPath: string;
  private readonly onSessionExpired: (() => void | Promise<void>) | undefined;
  private refreshInFlight: Promise<RefreshOutcome> | null = null;
  private sessionExpiryInFlight: Promise<void> | null = null;
  private sessionExpiredNotified = false;
  private user: User | null = null;

  constructor(options: MobileAuthClientOptions) {
    this.transport = options.transport;
    this.refreshTokenStorage = options.refreshTokenStorage;
    this.accessTokenStore =
      options.accessTokenStore ?? new MemoryAccessTokenStore(options.now ?? Date.now);
    this.clockSkewMilliseconds =
      options.clockSkewMilliseconds ?? DEFAULT_CLOCK_SKEW_MILLISECONDS;
    this.refreshPath = options.refreshPath ?? DEFAULT_REFRESH_PATH;
    this.onSessionExpired = options.onSessionExpired;
  }

  async setSession(tokens: MobileAuthTokens): Promise<void> {
    await this.refreshTokenStorage.write(tokens.refresh_token);
    this.accessTokenStore.set(tokens);
    this.user = tokens.user;
    this.sessionExpiredNotified = false;
  }

  getUser(): User | null {
    return this.user;
  }

  async restoreSession(): Promise<boolean> {
    if (this.accessTokenStore.getValid(this.clockSkewMilliseconds) !== null) {
      return true;
    }

    const outcome = await this.refreshOnce();
    if (outcome === "rejected") {
      await this.expireSession();
    }
    return outcome === "refreshed";
  }

  async clearSession(): Promise<void> {
    this.accessTokenStore.clear();
    this.user = null;
    await this.refreshTokenStorage.clear();
  }

  async request<TResponse>(request: TransportRequest): Promise<TResponse> {
    return this.executeWithAuthentication(request, (authenticatedRequest) =>
      this.transport.request<TResponse>(authenticatedRequest),
    );
  }

  async download(request: BinaryDownloadRequest): Promise<BinaryDownload> {
    return this.executeWithAuthentication(request, (authenticatedRequest) =>
      this.transport.download(authenticatedRequest),
    );
  }

  private async executeWithAuthentication<TRequest extends TransportRequest, TResponse>(
    request: TRequest,
    send: (authenticatedRequest: TRequest) => Promise<TResponse>,
  ): Promise<TResponse> {
    let accessToken = this.accessTokenStore.getValid(this.clockSkewMilliseconds);
    let initialRefreshOutcome: RefreshOutcome | null = null;
    if (accessToken === null) {
      initialRefreshOutcome = await this.refreshOnce();
      if (initialRefreshOutcome === "rejected") {
        await this.expireSession();
      }
      accessToken = this.accessTokenStore.getValid(this.clockSkewMilliseconds);
    }

    try {
      return await send(this.withAccessToken(request, accessToken));
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) {
        throw error;
      }

      if (initialRefreshOutcome !== null) {
        if (initialRefreshOutcome === "refreshed") {
          await this.expireSession();
        }
        throw error;
      }

      const refreshOutcome = await this.refreshOnce();
      if (refreshOutcome !== "refreshed") {
        await this.expireSession();
        throw error;
      }

      const retryToken = this.accessTokenStore.getValid(this.clockSkewMilliseconds);
      if (retryToken === null) {
        await this.expireSession();
        throw error;
      }

      try {
        return await send(this.withAccessToken(request, retryToken));
      } catch (retryError) {
        if (retryError instanceof ApiError && retryError.status === 401) {
          await this.expireSession();
        }
        throw retryError;
      }
    }
  }

  private withAccessToken<TRequest extends TransportRequest>(
    request: TRequest,
    accessToken: string | null,
  ): TRequest {
    if (accessToken === null) {
      return request;
    }

    return {
      ...request,
      headers: {
        ...request.headers,
        Authorization: `Bearer ${accessToken}`,
      },
    } as TRequest;
  }

  private refreshOnce(): Promise<RefreshOutcome> {
    if (this.refreshInFlight !== null) {
      return this.refreshInFlight;
    }

    const refreshPromise = this.performRefresh();
    this.refreshInFlight = refreshPromise;
    refreshPromise.then(
      () => {
        if (this.refreshInFlight === refreshPromise) {
          this.refreshInFlight = null;
        }
      },
      () => {
        if (this.refreshInFlight === refreshPromise) {
          this.refreshInFlight = null;
        }
      },
    );
    return refreshPromise;
  }

  private async performRefresh(): Promise<RefreshOutcome> {
    const refreshToken = await this.refreshTokenStorage.read();
    if (refreshToken === null) {
      return "missing";
    }

    try {
      const tokens = await this.transport.request<MobileAuthTokens>({
        path: this.refreshPath,
        method: "POST",
        body: { refresh_token: refreshToken },
      });
      await this.setSession(tokens);
      return "refreshed";
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        return "rejected";
      }
      throw error;
    }
  }

  private expireSession(): Promise<void> {
    if (this.sessionExpiryInFlight !== null) {
      return this.sessionExpiryInFlight;
    }

    const expiryPromise = this.performSessionExpiry();
    this.sessionExpiryInFlight = expiryPromise;
    expiryPromise.then(
      () => {
        if (this.sessionExpiryInFlight === expiryPromise) {
          this.sessionExpiryInFlight = null;
        }
      },
      () => {
        if (this.sessionExpiryInFlight === expiryPromise) {
          this.sessionExpiryInFlight = null;
        }
      },
    );
    return expiryPromise;
  }

  private async performSessionExpiry(): Promise<void> {
    this.accessTokenStore.clear();
    this.user = null;
    await this.refreshTokenStorage.clear();
    if (this.sessionExpiredNotified) {
      return;
    }
    this.sessionExpiredNotified = true;
    await this.onSessionExpired?.();
  }
}
