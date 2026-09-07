import { expect, it } from "vitest";

import type { User } from "@fitician/core/auth";

import { mobileRouteSnapshotFromAuth } from "./authContext";
import type { MobileAuthSessionSnapshot } from "./authSession";

const user: User = {
  created_at: "2026-01-01T00:00:00Z",
  email: "member@example.com",
  id: "member-1",
  is_admin: false,
  phone_number: null,
};

function auth(overrides: Partial<MobileAuthSessionSnapshot> = {}): MobileAuthSessionSnapshot {
  return {
    busy: false,
    sessionExpired: false,
    startupError: false,
    status: "signed_out",
    user: null,
    ...overrides,
  };
}

it("maps a signed-out auth state to a safe route snapshot", () => {
  expect(mobileRouteSnapshotFromAuth(auth())).toMatchObject({
    session: { status: "signed_out", user: null },
    specialistAccess: { coach: "denied", physician: "denied" },
  });
});

it("maps a signed-in auth state to onboarding until profile authority is loaded", () => {
  expect(
    mobileRouteSnapshotFromAuth(auth({ status: "signed_in", user, sessionExpired: false })),
  ).toMatchObject({
    profile: {
      completionState: "product_mode_not_selected",
      productMode: null,
      status: "resolved",
    },
    session: { status: "signed_in", user },
  });
});

it("preserves the session-expired signal for the sign-in flow", () => {
  expect(mobileRouteSnapshotFromAuth(auth({ sessionExpired: true }))).toMatchObject({
    session: { sessionExpired: true },
  });
});
