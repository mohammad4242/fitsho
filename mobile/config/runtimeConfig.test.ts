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

it("fails closed when development API configuration is absent", () => {
  expect(() => mobileRuntimeConfigFromExtra({})).toThrow(/required/u);
});

it("fails closed to release semantics for an invalid explicit environment", () => {
  expect(() => mobileRuntimeConfigFromExtra({ environment: "unexpected" })).toThrow(/production/u);
});
