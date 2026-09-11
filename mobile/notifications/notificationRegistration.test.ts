import { expect, it, vi } from "vitest";

import { registerAndroidNotifications, registerNotifications } from "./notificationRegistration";

it("registers the native Android FCM token after permission is ready", async () => {
  const register = vi.fn(async () => undefined);

  await expect(registerAndroidNotifications({
    prepare: async () => "granted",
    getToken: async () => "native-fcm-token",
    register,
  })).resolves.toBe("registered");

  expect(register).toHaveBeenCalledWith("native-fcm-token");
});

it("does not register a token after a denied permission or when native token access is absent", async () => {
  const register = vi.fn(async () => undefined);

  await expect(registerAndroidNotifications({
    prepare: async () => "denied",
    getToken: async () => "native-fcm-token",
    register,
  })).resolves.toBe("permission_denied");
  await expect(registerAndroidNotifications({
    prepare: async () => "not_required",
    getToken: async () => null,
    register,
  })).resolves.toBe("token_unavailable");

  expect(register).not.toHaveBeenCalled();
});

it("registers a native provider/token pair through the shared bootstrap", async () => {
  const register = vi.fn(async () => undefined);

  await expect(registerNotifications({
    prepare: async () => "granted",
    getToken: async () => ({ provider: "apns", token: "apns-token" }),
    register,
  })).resolves.toBe("registered");

  expect(register).toHaveBeenCalledWith({ provider: "apns", token: "apns-token" });
});
