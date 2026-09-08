import { expect, it } from "vitest";

import type { User } from "@fitician/core/auth";
import type { ProfileCompletionState } from "@fitician/core/profile";

import {
  defaultMobileRouteSnapshot,
  decideMobileRoute,
  type MobileRouteSnapshot,
} from "./navigation/routePolicy";

const member: User = {
  created_at: "2026-01-01T00:00:00Z",
  email: "member@example.com",
  id: "member-1",
  is_admin: false,
  phone_number: null,
};

function snapshot(overrides: Partial<MobileRouteSnapshot> = {}): MobileRouteSnapshot {
  return {
    ...defaultMobileRouteSnapshot,
    ...overrides,
  };
}

function signedIn(
  completionState: ProfileCompletionState,
  productMode: MobileRouteSnapshot["profile"]["productMode"] = "both",
  access: MobileRouteSnapshot["specialistAccess"] = defaultMobileRouteSnapshot.specialistAccess,
): MobileRouteSnapshot {
  return snapshot({
    profile: { completionState, productMode, status: "resolved" },
    session: { status: "signed_in", user: member },
    specialistAccess: access,
  });
}

it("keeps public and auth routes available only to signed-out users", () => {
  expect(decideMobileRoute("public", snapshot())).toEqual({ status: "allow" });
  expect(decideMobileRoute("auth", snapshot())).toEqual({ status: "allow" });
  expect(decideMobileRoute("public", signedIn("both_ready"))).toEqual({
    href: "/member",
    status: "redirect",
  });
  expect(decideMobileRoute("auth", signedIn("shared_profile_incomplete", null))).toEqual({
    href: "/onboarding",
    status: "redirect",
  });
});

it("requires a resolved profile before exposing onboarding or member routes", () => {
  expect(decideMobileRoute("member", snapshot())).toEqual({
    href: "/auth/sign-in",
    status: "redirect",
  });
  expect(
    decideMobileRoute(
      "member",
      snapshot({ session: { status: "signed_in", user: member } }),
    ),
  ).toEqual({ status: "loading" });
  expect(decideMobileRoute("onboarding", signedIn("shared_profile_incomplete", null))).toEqual({
    status: "allow",
  });
  expect(decideMobileRoute("member", signedIn("shared_profile_incomplete", null))).toEqual({
    href: "/onboarding",
    status: "redirect",
  });
  expect(decideMobileRoute("member", signedIn("both_ready"))).toEqual({ status: "allow" });
});

it("enforces training and nutrition product capabilities", () => {
  const training = signedIn("training_ready", "training");
  const nutrition = signedIn("nutrition_ready", "nutrition");
  const combined = signedIn("both_ready", "both");

  expect(decideMobileRoute("member", training, "training")).toEqual({ status: "allow" });
  expect(decideMobileRoute("member", training, "nutrition")).toEqual({
    href: "/member",
    status: "redirect",
  });
  expect(decideMobileRoute("member", nutrition, "nutrition")).toEqual({ status: "allow" });
  expect(decideMobileRoute("member", nutrition, "training")).toEqual({
    href: "/member",
    status: "redirect",
  });
  expect(decideMobileRoute("member", combined, "training")).toEqual({ status: "allow" });
  expect(decideMobileRoute("member", combined, "nutrition")).toEqual({ status: "allow" });
});

it("requires backend-confirmed specialist access and never treats admin as a role", () => {
  const adminOnlyBase = signedIn("both_ready", "both", { coach: "denied", physician: "denied" });
  const adminOnly = {
    ...adminOnlyBase,
    session: { ...adminOnlyBase.session, user: { ...member, is_admin: true } },
  } satisfies MobileRouteSnapshot;

  expect(decideMobileRoute("coach", adminOnly)).toEqual({
    href: "/member",
    status: "redirect",
  });
  expect(decideMobileRoute("physician", adminOnly)).toEqual({
    href: "/member",
    status: "redirect",
  });
  expect(
    decideMobileRoute("coach", signedIn("both_ready", "both", { coach: "granted", physician: "denied" })),
  ).toEqual({ status: "allow" });
  expect(
    decideMobileRoute("physician", signedIn("both_ready", "both", { coach: "denied", physician: "granted" })),
  ).toEqual({ status: "allow" });
  expect(
    decideMobileRoute("coach", signedIn("both_ready", "both", { coach: "loading", physician: "denied" })),
  ).toEqual({ status: "loading" });
});

it("surfaces profile and specialist transport failures instead of redirecting", () => {
  const profileError = {
    ...signedIn("both_ready"),
    profile: { completionState: null, productMode: null, status: "error" as const },
  };
  expect(decideMobileRoute("member", profileError)).toEqual({
    resource: "profile",
    status: "error",
  });
  expect(decideMobileRoute("auth", profileError)).toEqual({
    resource: "profile",
    status: "error",
  });

  const specialistError = {
    ...signedIn("both_ready"),
    specialistAccess: { coach: "error" as const, physician: "denied" as const },
  } as unknown as MobileRouteSnapshot;
  expect(decideMobileRoute("coach", specialistError)).toEqual({
    resource: "coach",
    status: "error",
  });
});

it("routes an expired session back to sign-in with an explicit recovery reason", () => {
  expect(
    decideMobileRoute(
      "member",
      snapshot({
        session: { sessionExpired: true, status: "signed_out", user: null },
      }),
    ),
  ).toEqual({ href: "/auth/sign-in?reason=session-expired", status: "redirect" });
});
