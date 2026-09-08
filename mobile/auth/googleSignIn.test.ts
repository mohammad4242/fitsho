import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import * as runtimeConfig from "../config/runtimeConfig";

type RuntimeClientConfig = {
  readonly googleAndroidClientId: string | null;
  readonly googleIosClientId: string | null;
};

it("selects the platform-specific Google client ID and disables missing platforms", () => {
  const selectClientId = (
    runtimeConfig as unknown as {
      googleClientIdForPlatform?: (
        platform: string,
        config: RuntimeClientConfig,
      ) => string | null;
    }
  ).googleClientIdForPlatform;

  expect(selectClientId).toEqual(expect.any(Function));
  if (typeof selectClientId !== "function") return;

  const config = {
    googleAndroidClientId: "android-client.apps.googleusercontent.com",
    googleIosClientId: "ios-client.apps.googleusercontent.com",
  };
  expect(selectClientId("android", config)).toBe(config.googleAndroidClientId);
  expect(selectClientId("ios", config)).toBe(config.googleIosClientId);
  expect(selectClientId("ios", { ...config, googleIosClientId: null })).toBeNull();
});

it("configures Expo Auth Session with the native platform client ID", async () => {
  const source = await readFile(resolve(__dirname, "GoogleSignIn.tsx"), "utf8");

  expect(source).toMatch(/Platform\.OS/);
  expect(source).toMatch(/iosClientId/);
  expect(source).toMatch(/googleClientIdForPlatform/);
  expect(source).toMatch(/available\s*=\s*clientId\s*!==\s*null/u);
});
