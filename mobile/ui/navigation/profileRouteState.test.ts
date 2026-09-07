import { expect, it } from "vitest";

import { mobileProfileStateFromStatus } from "./profileRouteState";

it("maps backend profile status into the native route guard state", () => {
  expect(
    mobileProfileStateFromStatus({
      user_id: "user-1",
      product_mode: "both",
      completion_state: "both_ready",
    }),
  ).toEqual({
    completionState: "both_ready",
    productMode: "both",
    status: "resolved",
  });
});

it("keeps incomplete backend states inside onboarding", () => {
  expect(
    mobileProfileStateFromStatus({
      user_id: "user-1",
      product_mode: "nutrition",
      completion_state: "nutrition_onboarding_incomplete",
    }),
  ).toMatchObject({
    completionState: "nutrition_onboarding_incomplete",
    productMode: "nutrition",
    status: "resolved",
  });
});
