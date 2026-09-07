import { expect, it, vi } from "vitest";

vi.mock("react-native", () => ({ Platform: { OS: "android" } }));
vi.mock("expo-constants", () => ({ default: { deviceName: "Test device", expoConfig: { version: "0.1.0" } } }));
vi.mock("expo-secure-store", () => ({
  getItemAsync: vi.fn(),
  setItemAsync: vi.fn(),
}));
vi.mock("expo-crypto", () => ({ randomUUID: vi.fn(() => "generated-device") }));

import { resolveMobileClientMetadata, type DeviceIdStorage } from "./deviceMetadata";

function storage(initial: string | null = null): DeviceIdStorage & { value: string | null } {
  return {
    value: initial,
    read: async function read() {
      return this.value;
    },
    write: async function write(value) {
      this.value = value;
    },
  };
}

it("persists one opaque device id for all native auth requests", async () => {
  const deviceStorage = storage();
  let generated = 0;
  const options = {
    appVersion: "0.1.0",
    createId: () => `device-${++generated}`,
    deviceName: "Pixel",
    platform: "android" as const,
    storage: deviceStorage,
  };

  await expect(resolveMobileClientMetadata(options)).resolves.toEqual({
    app_version: "0.1.0",
    device_id: "device-1",
    device_name: "Pixel",
    platform: "android",
  });
  await expect(resolveMobileClientMetadata(options)).resolves.toEqual({
    app_version: "0.1.0",
    device_id: "device-1",
    device_name: "Pixel",
    platform: "android",
  });
  expect(generated).toBe(1);
});

it("rejects empty generated device ids instead of sending invalid metadata", async () => {
  await expect(
    resolveMobileClientMetadata({
      appVersion: "0.1.0",
      createId: () => "",
      platform: "android",
      storage: storage(),
    }),
  ).rejects.toThrow("device id");
});
