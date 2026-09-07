import type { MobileRouteSnapshot } from "../ui/navigation/routePolicy";

import type { MobileAuthSessionSnapshot } from "./authSession";

export function mobileRouteSnapshotFromAuth(
  auth: MobileAuthSessionSnapshot,
): MobileRouteSnapshot {
  const signedIn = auth.status === "signed_in" && auth.user !== null;
  return {
    profile: {
      completionState: signedIn ? "product_mode_not_selected" : null,
      productMode: null,
      status: signedIn ? "resolved" : "loading",
    },
    session: {
      sessionExpired: auth.sessionExpired,
      status: auth.status,
      user: auth.user,
    },
    specialistAccess: {
      coach: "denied",
      physician: "denied",
    },
  };
}
