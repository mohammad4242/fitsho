import { expect, it } from "vitest";

import {
  PRODUCTION_API_BASE_URL,
  PRODUCTION_FRONTEND_ORIGIN,
} from "./productionApiConfig";
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

it("uses repository development endpoints when configuration is absent", () => {
  expect(mobileRuntimeConfigFromExtra({})).toEqual({
    appLinkHost: "app.fitician.example",
    apiBaseUrl: PRODUCTION_API_BASE_URL,
    environment: "development",
    frontendOrigin: PRODUCTION_FRONTEND_ORIGIN,
    googleAndroidClientId: null,
    googleIosClientId: null,
  });
});

it("fails closed to release semantics for an invalid explicit environment", () => {
  expect(() => mobileRuntimeConfigFromExtra({ environment: "unexpected" })).toThrow(/production/u);
});
