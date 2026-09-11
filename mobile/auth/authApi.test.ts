import { expect, it, vi } from "vitest";

import type { FiticianTransport, TransportRequest } from "@fitician/core";

import { createMobileAuthApi, type MobileClientMetadata } from "./authApi";

const metadata: MobileClientMetadata = {
  app_version: "0.1.0",
  device_id: "android-device-1",
  device_name: "Pixel",
  platform: "android",
};

function transport(responses: readonly unknown[]): FiticianTransport & { requests: TransportRequest[] } {
  const requests: TransportRequest[] = [];
  let index = 0;
  return {
    requests,
    download: vi.fn(),
    request: async <TResponse>(request: TransportRequest): Promise<TResponse> => {
      requests.push(request);
      return responses[index++] as TResponse;
    },
    upload: vi.fn(),
  };
}

it("sends native password credentials with device metadata", async () => {
  const nativeTransport = transport([{ user: { id: "member-1" } }]);
  const api = createMobileAuthApi(nativeTransport, metadata, "https://fitician.example");

  await api.signInWithPassword({ email: "member@example.com", password: "long password" });

  expect(nativeTransport.requests[0]).toEqual({
    body: {
      app_version: "0.1.0",
      device_id: "android-device-1",
      device_name: "Pixel",
      email: "member@example.com",
      password: "long password",
      platform: "android",
    },
    method: "POST",
    path: "/api/v1/auth/mobile/password",
  });
});

it("sends Apple identity credentials with iOS device metadata", async () => {
  const nativeTransport = transport([{ user: { id: "member-1" } }]);
  const api = createMobileAuthApi(
    nativeTransport,
    { ...metadata, platform: "ios", device_id: "iphone-device-1" },
  );

  await api.signInWithApple({
    email: "member@privaterelay.appleid.com",
    fullName: "Fitician Member",
    identityToken: "signed-apple-token",
    nonce: "nonce-1",
  });

  expect(nativeTransport.requests[0]).toEqual({
    body: {
      app_version: "0.1.0",
      device_id: "iphone-device-1",
      device_name: "Pixel",
      email: "member@privaterelay.appleid.com",
      full_name: "Fitician Member",
      identity_token: "signed-apple-token",
      nonce: "nonce-1",
      platform: "ios",
    },
    method: "POST",
    path: "/api/v1/auth/mobile/apple",
  });
});

it("uses shared public auth routes for registration, OTP, verification, and recovery", async () => {
  const nativeTransport = transport([{}, {}, {}, {}, undefined, {}, undefined]);
  const api = createMobileAuthApi(nativeTransport, metadata, "https://fitician.example");

  await api.register({ email: "member@example.com", password: "long password" });
  await api.sendPhoneOtp("09123456789");
  await api.verifyPhoneOtp("09123456789", "123456");
  await api.forgotPassword("member@example.com");
  await api.resetPassword("reset-token", "new password");
  await api.verifyEmail("verification-token");

  expect(nativeTransport.requests.map(({ path }) => path)).toEqual([
    "/api/v1/auth/register",
    "/api/v1/auth/mobile/phone/send-otp",
    "/api/v1/auth/mobile/phone/verify-otp",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/email/verify",
  ]);
  for (const request of nativeTransport.requests.filter(({ path }) => !path.includes("mobile/phone"))) {
    expect(request.headers).toEqual({ Origin: "https://fitician.example" });
  }
});
