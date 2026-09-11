import { expect, it } from "vitest";

import {
  IOS_CAMERA_USAGE_DESCRIPTION,
  applyIosHardening,
} from "./withIosHardening";

it("scopes HTTP ATS access to the configured Tailscale host", () => {
  const result = applyIosHardening(
    {
      NSAppTransportSecurity: {
        NSAllowsArbitraryLoads: true,
        NSExceptionDomains: {
          "existing.example": { NSExceptionAllowsInsecureHTTPLoads: true },
        },
      },
    },
    "http://100.97.78.5:8001",
  );

  expect(result.NSCameraUsageDescription).toBe(IOS_CAMERA_USAGE_DESCRIPTION);
  expect(result.NSAppTransportSecurity).toEqual({
    NSAllowsArbitraryLoads: false,
    NSExceptionDomains: {
      "existing.example": { NSExceptionAllowsInsecureHTTPLoads: true },
      "100.97.78.5": {
        NSExceptionAllowsInsecureHTTPLoads: true,
        NSIncludesSubdomains: false,
      },
    },
  });
});

it("does not create a broad HTTP exception for HTTPS runtimes", () => {
  const result = applyIosHardening({}, "https://api.fitician.example");

  expect(result.NSCameraUsageDescription).toBe(IOS_CAMERA_USAGE_DESCRIPTION);
  expect(result.NSAppTransportSecurity).toEqual({ NSAllowsArbitraryLoads: false });
});
