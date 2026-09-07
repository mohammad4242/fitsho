import type {
  Credentials,
  GenericMessage,
  MobileAuthTokens,
  PhoneOtpSent,
  User,
} from "@fitician/core/auth";
import type { FiticianTransport, TransportRequest } from "@fitician/core";

import type { MobileClientMetadata } from "./deviceMetadata";

export type { MobileClientMetadata } from "./deviceMetadata";

export interface MobileAuthApi {
  forgotPassword(email: string): Promise<GenericMessage>;
  register(credentials: Credentials): Promise<User>;
  resetPassword(token: string, password: string): Promise<void>;
  sendPhoneOtp(phoneNumber: string): Promise<PhoneOtpSent>;
  signInWithGoogle(credential: string): Promise<MobileAuthTokens>;
  signInWithPassword(credentials: Credentials): Promise<MobileAuthTokens>;
  verifyEmail(token: string): Promise<void>;
  verifyPhoneOtp(phoneNumber: string, code: string): Promise<MobileAuthTokens>;
}

export type MobileClientMetadataSource =
  | MobileClientMetadata
  | (() => Promise<MobileClientMetadata>);

async function resolveMetadata(source: MobileClientMetadataSource): Promise<MobileClientMetadata> {
  return typeof source === "function" ? source() : source;
}

function publicRequest(
  path: string,
  body: TransportRequest["body"],
  trustedOrigin: string | null | undefined,
): TransportRequest {
  return {
    body,
    headers: trustedOrigin ? { Origin: trustedOrigin } : undefined,
    method: "POST",
    path,
  };
}

export function createMobileAuthApi(
  transport: FiticianTransport,
  metadata: MobileClientMetadataSource,
  trustedOrigin?: string | null,
): MobileAuthApi {
  return {
    async forgotPassword(email) {
      return transport.request<GenericMessage>(
        publicRequest("/api/v1/auth/forgot-password", { email }, trustedOrigin),
      );
    },

    async register(credentials) {
      return transport.request<User>(
        publicRequest("/api/v1/auth/register", credentials, trustedOrigin),
      );
    },

    async resetPassword(token, password) {
      await transport.request<void>(
        publicRequest("/api/v1/auth/reset-password", { password, token }, trustedOrigin),
      );
    },

    async sendPhoneOtp(phoneNumber) {
      return transport.request<PhoneOtpSent>({
        body: { phone_number: phoneNumber },
        method: "POST",
        path: "/api/v1/auth/mobile/phone/send-otp",
      });
    },

    async signInWithGoogle(credential) {
      const clientMetadata = await resolveMetadata(metadata);
      return transport.request<MobileAuthTokens>({
        body: { ...clientMetadata, credential },
        method: "POST",
        path: "/api/v1/auth/mobile/google",
      });
    },

    async signInWithPassword(credentials) {
      const clientMetadata = await resolveMetadata(metadata);
      return transport.request<MobileAuthTokens>({
        body: { ...clientMetadata, ...credentials },
        method: "POST",
        path: "/api/v1/auth/mobile/password",
      });
    },

    async verifyEmail(token) {
      await transport.request<void>(
        publicRequest("/api/v1/auth/email/verify", { token }, trustedOrigin),
      );
    },

    async verifyPhoneOtp(phoneNumber, code) {
      const clientMetadata = await resolveMetadata(metadata);
      return transport.request<MobileAuthTokens>({
        body: { ...clientMetadata, code, phone_number: phoneNumber },
        method: "POST",
        path: "/api/v1/auth/mobile/phone/verify-otp",
      });
    },
  };
}
