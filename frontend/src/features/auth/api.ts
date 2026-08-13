import { ApiError, request } from "../../shared/apiClient";
import type { Credentials, GenericMessage, PhoneOtpSent, User } from "./types";

export function register(credentials: Credentials): Promise<User> {
  return request<User>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
}

export function login(credentials: Credentials): Promise<User> {
  return request<User>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials),
  });
}

export function forgotPassword(email: string): Promise<GenericMessage> {
  return request<GenericMessage>("/api/v1/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function resetPassword(token: string, password: string): Promise<void> {
  return request<void>("/api/v1/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  });
}

export function sendPhoneOtp(phoneNumber: string): Promise<PhoneOtpSent> {
  return request<PhoneOtpSent>("/api/v1/auth/phone/send-otp", {
    method: "POST",
    body: JSON.stringify({ phone_number: phoneNumber }),
  });
}

export function verifyPhoneOtp(phoneNumber: string, code: string): Promise<User> {
  return request<User>("/api/v1/auth/phone/verify-otp", {
    method: "POST",
    body: JSON.stringify({ phone_number: phoneNumber, code }),
  });
}

export function logout(): Promise<void> {
  return request<void>("/api/v1/auth/logout", { method: "POST" });
}

export async function getCurrentUser(): Promise<User | null> {
  try {
    return await request<User>("/api/v1/auth/me");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null;
    }
    throw error;
  }
}
