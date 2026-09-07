import type { ProfileStatusResponse } from "@fitician/core/profile";

export type MobileProfileRouteState = {
  readonly completionState: ProfileStatusResponse["completion_state"];
  readonly productMode: ProfileStatusResponse["product_mode"];
  readonly status: "resolved";
};

export function mobileProfileStateFromStatus(
  status: ProfileStatusResponse,
): MobileProfileRouteState {
  return {
    completionState: status.completion_state,
    productMode: status.product_mode,
    status: "resolved",
  };
}
