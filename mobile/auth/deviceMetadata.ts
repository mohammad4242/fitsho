import * as Crypto from "expo-crypto";
import Constants from "expo-constants";
import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

export const DEVICE_ID_KEY = "fitician.auth.device-id";

export interface DeviceIdStorage {
  read(): Promise<string | null>;
  write(value: string): Promise<void>;
}

export interface MobileClientMetadata {
  readonly app_version: string;
  readonly device_id: string;
  readonly device_name: string | null;
  readonly platform: "android" | "ios";
}

export interface ResolveMobileClientMetadataOptions {
  readonly appVersion?: string;
  readonly createId?: () => string;
  readonly deviceName?: string | null;
  readonly platform?: "android" | "ios";
  readonly storage?: DeviceIdStorage;
}

const secureDeviceIdStorage: DeviceIdStorage = {
  read: () => SecureStore.getItemAsync(DEVICE_ID_KEY),
  write: (value) => SecureStore.setItemAsync(DEVICE_ID_KEY, value),
};

function normalized(value: string | null | undefined): string | null {
  const result = value?.trim() ?? "";
  return result === "" ? null : result;
}

function nativePlatform(): "android" | "ios" {
  if (Platform.OS === "android" || Platform.OS === "ios") {
    return Platform.OS;
  }
  throw new Error("Fitician mobile authentication requires a native platform");
}

export async function resolveMobileClientMetadata(
  options: ResolveMobileClientMetadataOptions = {},
): Promise<MobileClientMetadata> {
  const storage = options.storage ?? secureDeviceIdStorage;
  const storedId = normalized(await storage.read());
  const deviceId = storedId ?? normalized((options.createId ?? Crypto.randomUUID)());
  if (deviceId === null) {
    throw new Error("A valid device id is required for mobile authentication");
  }
  if (storedId === null) {
    await storage.write(deviceId);
  }

  const appVersion = normalized(options.appVersion ?? Constants.expoConfig?.version);
  if (appVersion === null) {
    throw new Error("A valid app version is required for mobile authentication");
  }

  return {
    app_version: appVersion,
    device_id: deviceId,
    device_name: normalized(options.deviceName ?? Constants.deviceName),
    platform: options.platform ?? nativePlatform(),
  };
}
