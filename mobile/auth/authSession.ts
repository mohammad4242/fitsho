import type {
  Credentials,
  GenericMessage,
  MobileAuthTokens,
  RefreshTokenStorage,
  User,
} from "@fitician/core/auth";
import type {
  FiticianTransport,
  MultipartUploadRequest,
  TransportRequest,
} from "@fitician/core";

import { MobileAuthClient } from "./authClient";
import { createMobileAuthApi, type MobileAuthApi, type MobileClientMetadataSource } from "./authApi";

export type MobileAuthSessionStatus = "loading" | "signed_in" | "signed_out";

export interface MobileAuthSessionSnapshot {
  readonly busy: boolean;
  readonly sessionExpired: boolean;
  readonly startupError: boolean;
  readonly status: MobileAuthSessionStatus;
  readonly user: User | null;
}

export interface MobileAuthSessionOptions {
  readonly api?: MobileAuthApi;
  readonly metadata?: MobileClientMetadataSource;
  readonly refreshTokenStorage: RefreshTokenStorage;
  readonly transport: FiticianTransport;
  readonly trustedOrigin?: string | null;
}

export type MobileAuthSessionListener = (snapshot: MobileAuthSessionSnapshot) => void;

const signedOutSnapshot: MobileAuthSessionSnapshot = {
  busy: false,
  sessionExpired: false,
  startupError: false,
  status: "signed_out",
  user: null,
};

export class MobileAuthSession {
  private readonly api: MobileAuthApi;
  private readonly client: MobileAuthClient;
  private readonly listeners = new Set<MobileAuthSessionListener>();
  private restoreInFlight: Promise<void> | null = null;
  private snapshot: MobileAuthSessionSnapshot = { ...signedOutSnapshot, status: "loading" };

  constructor(options: MobileAuthSessionOptions) {
    if (options.api === undefined && options.metadata === undefined) {
      throw new Error("Mobile auth metadata is required");
    }
    this.api = options.api ?? createMobileAuthApi(
      options.transport,
      options.metadata as MobileClientMetadataSource,
      options.trustedOrigin,
    );
    this.client = new MobileAuthClient({
      onSessionExpired: () => this.handleSessionExpired(),
      refreshTokenStorage: options.refreshTokenStorage,
      transport: options.transport,
    });
  }

  getSnapshot(): MobileAuthSessionSnapshot {
    return this.snapshot;
  }

  subscribe(listener: MobileAuthSessionListener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  async restore(): Promise<void> {
    if (this.restoreInFlight !== null) {
      return this.restoreInFlight;
    }
    const restorePromise = this.restoreInternal();
    this.restoreInFlight = restorePromise;
    restorePromise.then(
      () => {
        if (this.restoreInFlight === restorePromise) this.restoreInFlight = null;
      },
      () => {
        if (this.restoreInFlight === restorePromise) this.restoreInFlight = null;
      },
    );
    return restorePromise;
  }

  async register(credentials: Credentials): Promise<User> {
    return this.run(async () => {
      const user = await this.api.register(credentials);
      const tokens = await this.api.signInWithPassword(credentials);
      await this.adopt(tokens);
      return user;
    });
  }

  async signInWithGoogle(credential: string): Promise<User> {
    return this.authenticate(() => this.api.signInWithGoogle(credential));
  }

  async signInWithPassword(credentials: Credentials): Promise<User> {
    return this.authenticate(() => this.api.signInWithPassword(credentials));
  }

  async sendPhoneOtp(phoneNumber: string): Promise<GenericMessage & { retry_after_seconds: number }> {
    return this.run(() => this.api.sendPhoneOtp(phoneNumber));
  }

  async verifyPhoneOtp(phoneNumber: string, code: string): Promise<User> {
    return this.authenticate(() => this.api.verifyPhoneOtp(phoneNumber, code));
  }

  async forgotPassword(email: string): Promise<GenericMessage> {
    return this.run(() => this.api.forgotPassword(email));
  }

  async resetPassword(token: string, password: string): Promise<void> {
    return this.run(() => this.api.resetPassword(token, password));
  }

  async verifyEmail(token: string): Promise<void> {
    return this.run(() => this.api.verifyEmail(token));
  }

  async sendEmailVerification(): Promise<GenericMessage> {
    return this.run(() => this.client.request<GenericMessage>({
      method: "POST",
      path: "/api/v1/auth/email/send-verification",
    }));
  }

  async request<TResponse>(request: TransportRequest): Promise<TResponse> {
    return this.client.request<TResponse>(request);
  }

  async upload<TResponse>(request: MultipartUploadRequest): Promise<TResponse> {
    return this.client.upload<TResponse>(request);
  }

  async logout(): Promise<void> {
    await this.logoutAt("/api/v1/auth/mobile/logout");
  }

  async logoutAll(): Promise<void> {
    await this.logoutAt("/api/v1/auth/mobile/logout-all");
  }

  private async restoreInternal(): Promise<void> {
    this.publish({ busy: true, status: "loading", startupError: false });
    try {
      const restored = await this.client.restoreSession();
      const user = this.client.getUser();
      this.publish({
        busy: false,
        sessionExpired: restored ? false : this.snapshot.sessionExpired,
        startupError: false,
        status: restored && user !== null ? "signed_in" : "signed_out",
        user: restored && user !== null ? user : null,
      });
    } catch {
      this.publish({ busy: false, startupError: true, status: "signed_out", user: null });
    }
  }

  private async authenticate(
    operation: () => Promise<MobileAuthTokens>,
  ): Promise<User> {
    return this.run(async () => {
      const tokens = await operation();
      await this.adopt(tokens);
      return tokens.user;
    });
  }

  private async adopt(tokens: MobileAuthTokens): Promise<void> {
    await this.client.setSession(tokens);
    this.publish({
      busy: true,
      sessionExpired: false,
      startupError: false,
      status: "signed_in",
      user: tokens.user,
    });
  }

  private async run<T>(operation: () => Promise<T>): Promise<T> {
    this.publish({ busy: true, startupError: false });
    try {
      return await operation();
    } finally {
      this.publish({ busy: false });
    }
  }

  private async logoutAt(path: string): Promise<void> {
    try {
      if (this.snapshot.status === "signed_in") {
        await this.client.request<void>({ method: "POST", path });
      }
    } finally {
      await this.client.clearSession();
      this.publish({
        busy: false,
        sessionExpired: false,
        startupError: false,
        status: "signed_out",
        user: null,
      });
    }
  }

  private handleSessionExpired(): void {
    this.publish({
      busy: false,
      sessionExpired: true,
      startupError: false,
      status: "signed_out",
      user: null,
    });
  }

  private publish(patch: Partial<MobileAuthSessionSnapshot>): void {
    this.snapshot = { ...this.snapshot, ...patch };
    for (const listener of this.listeners) listener(this.snapshot);
  }
}
