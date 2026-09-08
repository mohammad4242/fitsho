import { expect, it } from "vitest";
import { ApiError } from "@fitician/core";

import * as profileRouteState from "./profileRouteState";
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

it("keeps network and server failures explicit and allows a successful retry", async () => {
  const loadProfileStatus = (
    profileRouteState as unknown as {
      loadMobileProfileStatus?: (
        request: <TResponse>(input: { method: "GET"; path: string }) => Promise<TResponse>,
      ) => Promise<unknown>;
    }
  ).loadMobileProfileStatus;

  expect(loadProfileStatus).toEqual(expect.any(Function));
  if (typeof loadProfileStatus !== "function") return;

  let attempt = 0;
  const request = async <TResponse>(_input: { method: "GET"; path: string }) => {
    attempt += 1;
    if (attempt === 1) throw new TypeError("Network request failed");
    if (attempt === 2) throw new ApiError(500, "Service unavailable");
    return {
      user_id: "user-1",
      product_mode: "both",
      completion_state: "both_ready",
    } as TResponse;
  };

  await expect(loadProfileStatus(request)).resolves.toMatchObject({ status: "error" });
  await expect(loadProfileStatus(request)).resolves.toMatchObject({ status: "error" });
  await expect(loadProfileStatus(request)).resolves.toMatchObject({
    completionState: "both_ready",
    productMode: "both",
    status: "resolved",
  });
});
