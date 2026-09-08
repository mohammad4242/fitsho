import { expect, it } from "vitest";

import { mobileRuntimeConfigFromExtra } from "./runtimeConfig";

it("normalizes the native API, trusted web origin, and optional Google client config", () => {
  expect(
    mobileRuntimeConfigFromExtra({
      environment: "preview",
      apiBaseUrl: "https://api.fitician.example/",
      frontendOrigin: "https://fitician.example/",
      googleAndroidClientId: "android-client.apps.googleusercontent.com",
      googleIosClientId: "ios-client.apps.googleusercontent.com",
    }),
  ).toEqual({
    appLinkHost: "app.fitician.example",
    apiBaseUrl: "https://api.fitician.example",
    environment: "preview",
    frontendOrigin: "https://fitician.example",
    googleAndroidClientId: "android-client.apps.googleusercontent.com",
    googleIosClientId: "ios-client.apps.googleusercontent.com",
  });
});

it("uses safe development defaults when optional Expo extra values are absent", () => {
  expect(mobileRuntimeConfigFromExtra({})).toEqual({
    appLinkHost: "app.fitician.example",
    apiBaseUrl: "http://10.0.2.2:8001",
    environment: "development",
    frontendOrigin: "http://localhost:5173",
    googleAndroidClientId: null,
    googleIosClientId: null,
  });
});

it("fails closed to release semantics for an invalid explicit environment", () => {
  expect(mobileRuntimeConfigFromExtra({ environment: "unexpected" }).environment).toBe("production");
});
