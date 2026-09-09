import { expect, it } from "vitest";

import { onboardingRoute, publicOnboardingParams, PUBLIC_ONBOARDING_SOURCE } from "./authRoute";

it("keeps ordinary authentication on the existing onboarding route", () => {
  expect(onboardingRoute()).toBe("/onboarding");
  expect(publicOnboardingParams()).toBeUndefined();
});

it("preserves the public onboarding handoff through auth", () => {
  expect(onboardingRoute(PUBLIC_ONBOARDING_SOURCE)).toEqual({
    params: { source: PUBLIC_ONBOARDING_SOURCE },
    pathname: "/onboarding",
  });
  expect(publicOnboardingParams(PUBLIC_ONBOARDING_SOURCE)).toEqual({
    source: PUBLIC_ONBOARDING_SOURCE,
  });
});
