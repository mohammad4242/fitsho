import { expect, it, vi } from "vitest";

const runtime = vi.hoisted(() => ({
  getMobileRuntimeConfig: vi.fn(() => ({
    apiBaseUrl: "https://api.fitician.example",
    appLinkHost: "preview.fitician.example",
    frontendOrigin: "https://fitician.example",
    googleAndroidClientId: null,
    googleIosClientId: null,
    environment: "preview",
  })),
}));

vi.mock("../config/nativeRuntimeConfig", () => runtime);

import { redirectSystemPath } from "../app/+native-intent";

it("passes verified App Link intents through the authenticated native route filter", async () => {
  await expect(
    redirectSystemPath({
      initial: true,
      path: "https://preview.fitician.example/link/member/plans/plan-1",
    }),
  ).resolves.toBe("/member/workouts?planId=plan-1");
  await expect(
    redirectSystemPath({
      initial: false,
      path: "https://app.fitician.example/link/member/plans/plan-1",
    }),
  ).resolves.toBe("/");
});

it("leaves the Expo Development Client URL unmodified", async () => {
  await expect(
    redirectSystemPath({
      initial: true,
      path: "fitician://expo-development-client/?url=exp%3A%2F%2F10.0.2.2%3A8081",
    }),
  ).resolves.toBeNull();
});

it("leaves the native OAuth callback for Auth Session untouched", async () => {
  await expect(
    redirectSystemPath({
      initial: false,
      path: "com.fitician.app:/oauthredirect?code=authorization-code&state=state-value",
    }),
  ).resolves.toBeNull();
  await expect(
    redirectSystemPath({
      initial: false,
      path: "fitician:///oauthredirect?error=access_denied&state=state-value",
    }),
  ).resolves.toBeNull();
});
